# robolabel macOS 双击分发重构计划

> 目标：打包产物为标准 macOS 应用包 `robolabel.app`，用户拷贝到 Mac（Apple Silicon）后**双击图标直接打开标注界面**，无需命令行、无需"右键→打开"（本机/受信任分发场景）。
>
> 现状版本：单文件可执行 `dist/robolabletools`（PyInstaller onefile，`console=False`）。README 已注明跨机会触发 Gatekeeper 拦截。

---

## 1. 现状盘点

### 1.1 当前打包方式（`robolabel.spec`）

| 项 | 现状 | 对"双击可用"的影响 |
| --- | --- | --- |
| 形态 | onefile 单文件 EXE（`dist/robolabletools`，约 155MB） | **非 `.app`**：Finder 双击裸 Mach-O 可执行文件体验差，可能被询问"用什么程序打开"；无图标、无 Dock 行为 |
| 终端窗口 | `console=False` | ✅ 已是 windowed 模式，双击不会弹终端 |
| 签名 | `codesign_identity=None`，无任何签名 | ❌ 拷贝到其他 Mac 触发 Gatekeeper 拦截（需右键打开或 codesign） |
| Info.plist | 无定制（仅 PyInstaller 默认最小 plist） | ❌ 无图标、无版本号、`NSHighResolutionCapable` 未声明（高分屏有模糊风险） |
| 图标 | 无 `.icns` | ❌ Finder/Dock 显示通用可执行文件图标 |
| ffmpeg | 运行时 `shutil.which("ffmpeg")` 依赖系统 PATH | ❌ **GUI 启动的 app PATH 只有 `/usr/bin:/bin:/usr/sbin:/sbin`**，不含 `/opt/homebrew/bin`（Apple Silicon 的 Homebrew 默认路径）→ `shutil.which` 找不到 ffmpeg，OpenCV 无法解码的编码（如 H.265/部分 .mov）全部失败 |
| 启动速度 | onefile 每次解压 ~150MB 到临时目录 | ⚠️ 冷启动慢（数秒），退出时清理临时目录偶发失败 |
| 日志 | windowed 模式 stdout/stderr 不可见 | ⚠️ 崩溃/报错无法排障 |

### 1.2 已经没问题、重构**不需要**动的部分

- **数据写入路径**：所有标注数据、技能库都写入用户**打开的数据集目录**（`<dataset_root>/lite_annotations/`，见 `annotation_store.py:21-26`、`skill_library.py:15-16`），不写应用包内部 → 无 `.app` 只读/沙盒权限问题。
- **config 读取**：`vocabulary.py:7`、`skill_form.py:27`、`segment_editor.py:28` 用 `Path(__file__).resolve().parent.parent / "config"`。在 onedir/BUNDLE 布局下 `config` 与包同级，当前成立；但依赖目录巧合，建议顺手收敛为统一 helper（见 3.3）。
- **HiDPI**：`app.py:20-21` 已启用 `AA_EnableHighDpiScaling`/`AA_UseHighDpiPixmaps`；但仍需在 Info.plist 显式声明 `NSHighResolutionCapable`。

### 1.3 运行环境基线

- 当前构建机：macOS（darwin/arm64），Python 3.9–3.13 + PyQt5。
- `requirements.txt`：`numpy / opencv-python / pyyaml / PyQt5 / pyinstaller`（pyinstaller 未锁版本，按 PyInstaller ≥ 6 规划）。

---

## 2. 目标与验收标准

### 2.1 目标

`dist/robolabel.app`（标准 macOS bundle）交付给用户后：

```text
用户拿到 robolabel.app → 拖入 /Applications（或直接双击）→ 界面打开 → 正常标注/保存/导出
```

### 2.2 验收标准

- [ ] 产物为 `robolabel.app`，Finder 显示自定义图标，无终端窗口
- [ ] 双击启动 < 5s，Retina 屏文字清晰不模糊
- [ ] 打开一个 OpenCV 解不了、必须 ffmpeg 兜底的视频样本，仍可播放（验证 PATH 注入或内嵌 ffmpeg 生效）
- [ ] 本机构建产物在本机双击直接可用（ad-hoc 签名生效）；分发场景给出签名/公证说明
- [ ] 打包前后 `python -m pytest tests` 全绿
- [ ] 崩溃/异常有日志落盘，便于反馈排障

---

## 3. 重构方案

### 3.1 打包形态：onedir + BUNDLE（产出 `.app`）

**不用 onefile 做 `.app`** 的理由：

- `.app` 内部其实天然是"目录结构"（`Contents/MacOS` + `Contents/Frameworks`），onefile 的自解压反而多一层临时目录，启动更慢；
- BUNDLE 形态签名简单可靠（整个包一条 `codesign --deep`），onefile 的 ad-hoc 签名/公证流程更脆弱；
- 后续要内嵌 ffmpeg 等资源，直接往 `Contents/Frameworks/bin` 放即可，无需改代码。

**新 spec 结构（实际实施，PyInstaller 6 三段式 `EXE(exclude_binaries) → COLLECT → BUNDLE`）**：

> 注：PyInstaller ≥ 6 的 `BUNDLE(完整 EXE)` 写法会把整个 onefile 塞进 `Contents/MacOS`，属于**已废弃**模式（源码内 `WINDOWED_ONEFILE_DEPRCATION` 警告），且会丢失 onedir 布局。必须用 `exclude_binaries=True` 的 EXE + COLLECT。

```python
# robolabel.spec（重构后）
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path.cwd()

config_files = [
    "coordination_modes.yaml",
    "lite_vocabulary.json",
    "phase_actions.json",
    "scene_templates.yaml",
    "skill_object_slots.json",
    "skill_templates.yaml",
]

a = Analysis(
    [str(ROOT / "lite_annotator" / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "config" / name), "config") for name in config_files],
    hiddenimports=["common.skill_schema"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "sam2", "segment_anything"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="robolabel",                # 可执行文件名（Contents/MacOS/robolabel）
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                       # ← 改为 False：arm64 上 UPX 无意义且会破坏 codesign
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                   # windowed：双击不弹终端
    disable_windowed_traceback=False,
    argv_emulation=True,             # ← 新增：支持 Finder 打开事件 / 拖文件到 Dock 图标
    target_arch=None,
    codesign_identity=None,          # 签名由 PyInstaller 构建时自动 ad-hoc 完成（勿再重签）
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="robolabel",
)
app = BUNDLE(
    coll,
    name="robolabel.app",
    icon=str(ROOT / "assets" / "app.icns"),          # ← 新增图标资源
    bundle_identifier="com.robolabel.app",
    info_plist={
        "CFBundleName": "robolabel",
        "CFBundleDisplayName": "RoboLabel",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,             # ← 高分屏关键
        "LSMinimumSystemVersion": "12.0",
        "NSHumanReadableCopyright": "robolabel contributors",
        # 可选：把默认 UI 缩放写进环境（等价于终端里的 ROBOLABEL_UI_SCALE）
        # "LSEnvironment": {"ROBOLABEL_UI_SCALE": "1.0"},
        # 可选：注册可打开的文件类型（配合 argv_emulation 双击关联文件）
        # "CFBundleDocumentTypes": [...],
    },
    version=None,
)
```

对照现有 spec 的改动点：

| # | 改动 | 原因 |
| --- | --- | --- |
| 1 | 去掉 `COLLECT` 需求，直接 `EXE → BUNDLE` | 产出标准 `.app`（PyInstaller ≥ 6 自动把二进制/资源放进 `Contents/Frameworks`、`Contents/Resources`） |
| 2 | `name="robolabletools"` → `"robolabel"` | 应用名统一；`.app` 名 = 用户看到的名字 |
| 3 | `upx=True` → `upx=False` | arm64 不支持/无效；UPX 压缩会破坏后续 codesign |
| 4 | 新增 `argv_emulation=True` | macOS 特有：让 Finder 打开事件（双击关联文件、拖文件到 Dock）能进 `sys.argv` |
| 5 | 新增 `BUNDLE(icon=..., bundle_identifier=..., info_plist=...)` | 图标、包 ID、高分屏声明、版本号 |

> 兼容性说明：若构建机 PyInstaller 是 5.x，则需改为 `COLLECT → BUNDLE` 的经典三段式写法；计划按 ≥ 6 执行，构建脚本里加版本断言（见 3.5）。

### 3.2 图标资源

- 新建 `assets/` 目录，提供 1024×1024 源图（PNG）。
- 用 macOS 自带工具生成 `.icns`：

```bash
mkdir -p assets/app.iconset
# 把 1024 源图缩放到 iconset 各规格（icon_16x16.png ... icon_512x512@2x.png）
iconutil -c icns assets/app.iconset -o assets/app.icns
```

- 若暂无可用的设计图，先用纯色占位 `.icns` 打通打包链路，后续替换（里程碑 M1/M3 分开排期）。

### 3.3 代码侧适配（小而关键）

#### 3.3.1 统一资源路径 helper（防布局巧合）

新增 `lite_annotator/paths.py`：

```python
from __future__ import annotations
import sys
from pathlib import Path

def resource_path(relative: str) -> Path:
    """打包（PyInstaller）后从应用包内取只读资源；源码运行时从项目根取。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative
```

把以下 3 处 `PROJECT_ROOT / "config" / ...` 替换为 `resource_path("config/...")`：

- `lite_annotator/vocabulary.py:7-8`（`lite_vocabulary.json`）
- `lite_annotator/skill_form.py:27-28`（`skill_object_slots.json`）
- `lite_annotator/segment_editor.py:28`（`phase_actions.json`）

> `sys._MEIPASS` 在 PyInstaller 的 onedir/BUNDLE 下指向 `Contents/Frameworks`，与 datas 落点一致；源码运行回退到项目根，行为不变。

#### 3.3.2 macOS GUI 启动的 PATH 注入（解决 ffmpeg 找不到）

GUI 启动（LaunchServices 双击）时 PATH 不包含 Homebrew 目录，而 `video_decode.py:77,131` 用 `shutil.which("ffmpeg"/"ffprobe")` 探测。在 `app.py` 的 `main()` 最前面注入：

```python
def ensure_macos_tool_path() -> None:
    """GUI 启动的 app PATH 很短，补上 Homebrew 常见目录，否则找不到 ffmpeg/ffprobe。"""
    extra = [
        "/opt/homebrew/bin",          # Apple Silicon Homebrew
        "/opt/homebrew/opt/ffmpeg/bin",
        "/usr/local/bin",             # Intel Homebrew / 其他
    ]
    current = os.environ.get("PATH", "")
    missing = [p for p in extra if p not in current.split(":")]
    if missing:
        os.environ["PATH"] = ":".join(missing + [current])
```

#### 3.3.3 ffmpeg 兜底策略（二选一，默认 A）

- **方案 A（默认，本期必做）**：PATH 注入 + 在界面对无法解码的视频给出**中文友好提示**（"未检测到 ffmpeg/ffprobe，请安装：brew install ffmpeg"）。`video_decode.py:130-138` 已有类似英文报错，改成从 UI 层捕获并展示中文提示即可。
- **方案 B（可选增强，依赖许可评估）**：把 ffmpeg/ffprobe 二进制拷进 `Contents/Frameworks/bin/`，`video_decode` 优先探测 `resource_path("bin/ffmpeg")` 再回退 PATH。注意：brew 的 ffmpeg 默认带 GPL 组件（x264 等），**对外分发需先做许可证评估**（可改用 LGPL 构建或仅对内部使用）。见 5.3 风险。

#### 3.3.4 日志落盘（windowed 排障出口）

`app.py` 增加：`logging` 输出到 `~/Library/Logs/robolabel/robolabel.log`（`QMessageBox` 弹错误时同时写日志）。优先级低，放 M4。

### 3.4 签名与 Gatekeeper（按分发场景分层）

| 场景 | 做法 | 双击效果 |
| --- | --- | --- |
| 本机构建、本机使用 | `codesign --force --deep -s - dist/robolabel.app`（ad-hoc） | ✅ 直接双击可用 |
| 局域网/组织内分发 | 自建证书 `codesign --options runtime -s "你的证书"` + 用户信任证书 | ✅ 直接双击可用 |
| 公网分发（推荐目标） | Developer ID 证书 + `notarytool submit` 公证 + `stapler staple` | ✅ 直接双击可用，无 Gatekeeper 弹窗 |

- Gatekeeper 判定：**下载/拷贝产生的 `com.apple.quarantine` 属性** + 签名状态。本机构建无 quarantine 属性，ad-hoc 签名即可双击；跨机分发必须走"签名 + 公证"或引导用户右键打开一次。
- 构建脚本里把 codesign 做成**必做步骤**（默认 ad-hoc），避免产出未签名产物。

```bash
codesign --force --deep --options runtime -s - dist/robolabel.app
# 验证：
codesign --verify --deep --strict --verbose=2 dist/robolabel.app
spctl --assess --type execute --verbose=4 dist/robolabel.app   # 公证后应 accepted
```

### 3.5 构建与验证脚本

新建 `scripts/build_macos.sh`（并在 README 更新打包章节）：

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="python3"
VERSION_OK=$("$PYTHON" -c 'import PyInstaller,sys; sys.exit(0 if int(PyInstaller.__version__.split(".")[0]) >= 6 else 1)')
if [ "$VERSION_OK" != "0" ]; then
  echo "需要 PyInstaller >= 6"; exit 1
fi

"$PYTHON" -m PyInstaller robolabel.spec --clean --noconfirm
codesign --force --deep --options runtime -s - "dist/robolabel.app"
codesign --verify --deep --strict --verbose=2 "dist/robolabel.app"
echo "产物: dist/robolabel.app"
```

**双击冒烟测试清单（验收用）**：

1. `open dist/robolabel.app`（等价 Finder 双击），确认窗口出现、无终端
2. 验证进程无窗口残留（`pgrep -lf robolabel`）
3. Retina 屏查看文字清晰度
4. 打开 H.265 / 高编码视频样本 → 正常播放（ffmpeg 兜底生效）
5. 完整走一遍：打开数据集 → 场景标注 → 片段标注 → 保存 → 导出标准 JSON
6. 卸载 ffmpeg 模拟环境（临时改 PATH）→ 确认出现中文提示而非静默失败
7. `python -m pytest tests` 全绿

### 3.6 测试与回归

- 现有 `tests/`（校验/导出/编辑器）不依赖 GUI 与打包路径，**不受影响**。
- 新增小测试（放 `tests/test_paths.py`）：
  - `resource_path` 在非冻结（源码）环境下返回项目根下路径；
  - `ensure_macos_tool_path` 把 `/opt/homebrew/bin` 注入且不重复追加。
- 打包产物验证放手工冒烟清单（自动 GUI 测试成本高，本期不做）。

---

## 4. 里程碑与排期

| 里程碑 | 内容 | 涉及文件 | 估时 |
| --- | --- | --- | --- |
| **M1 出包** | spec 改为 BUNDLE，产出 `robolabel.app`；占位 `.icns`；构建脚本 + ad-hoc 签名 | `robolabel.spec`、`assets/`、`scripts/build_macos.sh` | 0.5 天 |
| **M2 运行适配** | `paths.py` + 3 处替换；`ensure_macos_tool_path`；ffmpeg 缺失中文提示 | `lite_annotator/paths.py`、`vocabulary.py`、`skill_form.py`、`segment_editor.py`、`app.py`、`video_decode.py` | 0.5–1 天 |
| **M3 分发强化** | 正式图标；日志落盘；ffmpeg 内嵌（方案 B，含许可评估） | `assets/app.icns`、`app.py`、`video_decode.py`、构建脚本 | 1–2 天 |
| **M4 验收发布** | 双击冒烟全清单；pytest 回归 + 新增测试；README/分发文档（含公证指引） | `tests/test_paths.py`、`README.md`、`docs/` | 0.5–1 天 |

**M1 + M2 完成后即达成核心目标**（双击可用），M3/M4 为分发体验增强。

---

## 5. 风险与回退

| 风险 | 说明 | 应对 |
| --- | --- | --- |
| PyInstaller 版本差异 | 5.x 需 `COLLECT + BUNDLE` 写法 | 构建脚本断言 ≥ 6；README 锁定 `pyinstaller>=6` |
| arm64 与 Intel 双架构 | 默认仅 Apple Silicon；Intel 用户无法运行 | 本期定位 Apple Silicon；后续可用 universal2（需在 Intel 或 CI 双架构构建） |
| ffmpeg 内嵌的 GPL 许可 | brew ffmpeg 含 GPL 组件 | 默认方案 A（提示安装）；方案 B 仅在许可评估通过后启用 |
| PyQt5 wheel 上限 | PyQt5 官方 wheel 不支持更新 Python | 维持 Python ≤ 3.13（README 已有说明） |
| 公证门槛 | notarization 需要 Apple Developer 账号 | 计划提供指引；无账号则保持 ad-hoc + 右键打开说明 |
| 回退 | 新 spec 出问题 | 保留当前 onefile spec 为 `robolabel-onefile.spec`，可随时回退 |

---

## 6. 附：当前项目结构（重构涉及的路径）

```
robolabel/
├── robolabel.spec              # ← M1 重构
├── lite_annotator/
│   ├── app.py                  # ← M2 入口：PATH 注入 + 日志
│   ├── vocabulary.py           # ← M2 resource_path
│   ├── skill_form.py           # ← M2 resource_path
│   ├── segment_editor.py       # ← M2 resource_path
│   └── video_decode.py         # ← M2 ffmpeg 探测/提示
├── config/                     # 只读资源，随包分发（datas）
├── tests/                      # 回归（新增 test_paths.py）
├── assets/app.icns             # ← M1/M3 新增
├── scripts/build_macos.sh      # ← M1 新增
└── docs/macos-packaging-plan.md # 本文档
```

---

## 7. 实施记录（2026-08-11，M1–M4 已完成）

按本文档完成 mac 版开发与打包，实际落地与计划的差异及关键经验：

| # | 计划原文 | 实际做法 | 原因 |
| --- | --- | --- | --- |
| 1 | `BUNDLE(exe)` 直接写法 | 三段式 `EXE(exclude_binaries=True) → COLLECT → BUNDLE` | PyInstaller 6.22 中 `BUNDLE(完整 EXE)` 为废弃的 onefile-in-app 模式，产出会丢失 onedir 布局 |
| 2 | 占位图标用 PyQt5 生成 PNG | 纯 Python 标准库（zlib/struct）生成 PNG，`sips` 缩放 + `iconutil` 转 `.icns` | headless 会话下 QImage/QPainter 段错误；纯标准库零依赖更稳 |
| 3 | 构建脚本做 `codesign --force --deep -s -` | **不再二次签名**，只 `codesign --verify` | PyInstaller 构建 BUNDLE 时已自动 ad-hoc 签名；`--deep` 重签会破坏 bootloader 与嵌套框架（`com.apple.python3`）签名一致性，导致启动报 "different Team IDs" |
| 4 | 默认缓存目录 | 脚本内 `export PYINSTALLER_CONFIG_DIR=$HOME/.cache/pyinstaller` | 本机 `~/Library/Application Support` 被 TCC 拦截，PyInstaller 无法建缓存 |
| 5 | 日志落盘 `~/Library/Logs/robolabel/` | 保留，但 `setup_logging` 对 `OSError` 静默降级 | 部分环境同样拦截 `~/Library/Logs`；日志是辅助功能，不能让 app 启动失败 |
| 6 | ffmpeg 兜底方案 A | PATH 注入 `/opt/homebrew/bin` 等 + 缺失时中文提示（`video_decode.py`） | 已用模拟 GUI PATH（`/usr/bin:/bin:/usr/sbin:/sbin`）验证注入后 `shutil.which("ffmpeg")` 可命中 |

**验证结果**：

- `python -m pytest tests`：53 passed（含新增 `tests/test_paths.py` 3 例）
- `open dist/robolabel.app`（等价 Finder 双击）：进程存活，GUI 事件循环正常运行
- 产物 `dist/robolabel.app`：`codesign --verify --deep --strict` 通过（ad-hoc）
- Info.plist：`CFBundleIdentifier=com.robolabel.app`、`NSHighResolutionCapable=1`、版本 1.0.0 正确
- bundle 布局：`Contents/MacOS/robolabel`（bootloader）+ `Contents/Frameworks/`（Python3/PyQt5/cv2/config 6 个配置）+ `Contents/Resources/app.icns`

**待办（未做，按计划属可选增强）**：ffmpeg 内嵌（方案 B，需 GPL 许可评估）、正式设计稿图标（当前为占位 "RL" 图标）、Developer ID + notarization 公证（需开发者账号）。

### 7.1 追加：universal2 双架构（2026-08-11）

需求：产物不锁定架构，Apple Silicon 与 Intel Mac 均可运行。

**可行性调研结论**：numpy / opencv-python 等主流包**不提供 universal2 wheel**（numpy 仅 1.22 之前、opencv/pyyaml 完全没有），PyInstaller `--target-arch universal2` 只合并 bootloader，第三方 `.so` 仍需 universal2 → 方案 A（universal2 Python + universal2 依赖）不可行。

**落地方案（双构建 + lipo 合并）**：

1. `scripts/get_universal_python.sh`：从华为云镜像下载 python.org universal2 Python 3.12.10 pkg，`pkgutil --expand-full` 解包（无需 sudo），软链出 `Python.framework`；运行时需 `DYLD_FRAMEWORK_PATH` + `DYLD_LIBRARY_PATH`（解包内 OpenSSL）。
2. 两个 venv：`build-venv-arm64`（原生）+ `build-venv-x86`（`arch -x86_64` 下创建，Rosetta），依赖版本以 arm64 freeze 对齐。
3. spec 通过 `ROBOLABEL_TARGET_ARCH` 环境变量控制 `EXE(target_arch=...)`（`--target-architecture` 不能与 .spec 同用）。
4. 两次 PyInstaller onedir 构建（`--distpath dist-arm64/dist-x86`）→ `scripts/merge_universal.py` 以 arm64 版为基底，对每个非 fat 的 Mach-O 执行 `lipo -create` 合并（Qt/Python.framework 本身 universal2 则保留）→ 从内到外 ad-hoc 签名。
5. `scripts/patch_pyinstaller_dyld.py`：PyInstaller 隔离子进程只经 `arch -e` 传播 `DYLD_LIBRARY_PATH`，不传 `DYLD_FRAMEWORK_PATH`，解包 python 场景下子进程加载解释器必崩；该脚本幂等地补齐传播。

**验证**：bootloader 与 cv2/numpy/yaml/PyQt5/QtCore 全部为 `x86_64 arm64` fat；arm64 `open` 双击启动 OK；`arch -x86_64` 直跑 bootloader（Rosetta 模拟 Intel）启动 OK；pytest 53 passed；`codesign --verify` 通过。产物 `dist/robolabel.app` 约 360MB（双架构体积）。
