# robolabel Windows 版本开发计划

> 目标：将当前仅支持 macOS / Ubuntu 的 robolabel 适配为 Windows 版本，产出 `dist/robolabel/robolabel.exe`（PyInstaller onedir），用户在 Windows 上**双击即可打开标注界面**，无需命令行。
>
> 现状：macOS 版已落地（`docs/macos-packaging-plan.md`，universal2 `.app`）。本计划按同一套思路拆解 Windows 的代码适配与打包方案。

---

## 1. 现状盘点

### 1.1 代码层的平台差异（需要适配的只有 2 个文件）

| 位置 | 现状（macOS 特化） | Windows 影响 |
| --- | --- | --- |
| `lite_annotator/app.py:20-29` `ensure_macos_tool_path()` | 往 PATH 注入 Homebrew 目录，分隔符硬编码 `:` | **必须加平台守卫**。Windows PATH 分隔符是 `;`，且 Explorer 启动的 GUI 进程已继承用户+系统 PATH，无需注入。若不守卫，`split(":")` 会把整条 PATH 当作一项处理，行为不可预期 |
| `lite_annotator/app.py:32-48` `setup_logging()` | 日志写 `~/Library/Logs/robolabel/robolabel.log` | Windows 无 `Library/Logs` 目录，应写 `%LOCALAPPDATA%\robolabel\robolabel.log` |
| `lite_annotator/video_decode.py:135` | ffmpeg 缺失提示 `brew install ffmpeg` | Windows 应提示 `winget install`（见 4.4） |

**其余代码无需改动，天然跨平台**：

- `paths.py:9` 的 `sys._MEIPASS` 是 PyInstaller 官方通用机制，Windows 同样生效（onedir 下指向 `_internal` 目录）
- 数据写入数据集目录 `<dataset_root>/lite_annotations/`，不写安装目录 → 无权限问题
- HiDPI：`app.py:55-56` 的 `AA_EnableHighDpiScaling` 在 Qt5 Windows 平台生效，无需 `manifest` 级别设置
- 中文字体：`ui_theme.py:196-201` 用 `QFont(app.font())` 派生，未硬编码字体族，Windows 下 Qt 自动回退微软雅黑
- `os.dup` / `os.dup2`（`video_decode.py:229-232`）、`shutil.which`、`subprocess` 均为 Windows 支持的 POSIX 兼容 API
- `ffmpeg/ffprobe` 探测用 `shutil.which`，Windows 下查 PATH 中的 `ffmpeg.exe`，行为一致

### 1.2 打包层的平台差异

| 项 | macOS（现有） | Windows（计划） |
| --- | --- | --- |
| spec | `robolabel.spec`：`EXE → COLLECT → BUNDLE`（`.app` 外壳） | 新建 `robolabel-win.spec`：`EXE → COLLECT`（onedir 目录） |
| 窗口模式 | `console=False`（windowed） | 同样 `console=False`，PyInstaller 自动用 `pythonw` 语义 |
| argv 事件 | `argv_emulation=True` | **macOS 专属**，Windows 上无效，删除 |
| 图标 | `assets/app.icns` | 需生成 `assets/app.ico`（多尺寸，见 4.2） |
| 签名 | ad-hoc codesign + 公证 | SmartScreen 弹窗策略（见 4.5） |
| 构建脚本 | `scripts/build_macos.sh`（bash） | 新建 `scripts/build_windows.ps1`（PowerShell） |

### 1.3 运行环境基线（Windows）

- 系统：Windows 10 1809+ / Windows 11（x86_64）
- Python：3.9–3.13（PyQt5 官方 wheel 上限，同 README）
- 依赖：`requirements.txt` 全部有 `win_amd64` wheel（numpy / opencv-python / pyyaml / PyQt5 / pyinstaller）
- ffmpeg：`winget install Gyan.FFmpeg` 或 `choco install ffmpeg`（PATH 全局生效，Explorer 启动时继承）

---

## 2. 目标与验收标准

### 2.1 目标

```text
用户拿到 dist/robolabel/ 目录（含 robolabel.exe）→ 双击 → 界面打开 → 正常标注/保存/导出
```

### 2.2 验收标准

- [ ] 产物为 `dist/robolabel/robolabel.exe`（onedir），Finder 等价物（资源管理器）显示自定义图标，无控制台窗口
- [ ] 双击启动 < 5s，高分屏（125%/150% 缩放）文字清晰不模糊
- [ ] 打开 OpenCV 解不了的编码样本 → ffmpeg 兜底正常播放（或按 4.4 方案 B 内嵌 ffmpeg）
- [ ] 打包前后 `python -m pytest tests` 全绿
- [ ] 崩溃/异常有日志落盘 `%LOCALAPPDATA%\robolabel\robolabel.log`
- [ ] 路径含中文/空格的机器可正常启动、打开数据集

---

## 3. 代码适配（M2，小而关键）

### 3.1 `app.py`：平台守卫 + 日志路径平台化

```python
def ensure_platform_tool_path() -> None:
    """macOS GUI 启动的 app PATH 很短，补上 Homebrew 目录；其他平台无需处理。"""
    if sys.platform != "darwin":
        return
    current = os.environ.get("PATH", "")
    missing = [
        p for p in ("/opt/homebrew/bin", "/opt/homebrew/opt/ffmpeg/bin", "/usr/local/bin")
        if p not in current.split(":")
    ]
    if missing:
        os.environ["PATH"] = ":".join(missing + [current])
```

```python
def setup_logging() -> None:
    try:
        if sys.platform == "darwin":
            log_dir = Path.home() / "Library" / "Logs" / "robolabel"
        else:  # Windows / Linux
            base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".robolabel")
            log_dir = Path(base) / "robolabel"
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=log_dir / "robolabel.log", ...)
    except OSError:
        return
```

> 注意：原函数名 `ensure_macos_tool_path` 与调用处 `app.py:52` 同步更新；或保留原函数名、仅函数体加 `sys.platform != "darwin"` 守卫（改动更小）。测试 `tests/test_paths.py` 中若引用了原函数，需同步更新。

### 3.2 `video_decode.py`：ffmpeg 缺失提示平台化

```python
def _ffmpeg_install_hint() -> str:
    if sys.platform == "darwin":
        return "brew install ffmpeg"
    if sys.platform == "win32":
        return "winget install Gyan.FFmpeg"
    return "sudo apt install ffmpeg"
```

替换 `video_decode.py:135` 中硬编码的 `brew install ffmpeg`。

### 3.3 无需改动清单（明确验证过）

- `paths.py` — 通用
- `ui_theme.py` / 词表 / 校验 — 纯数据与 Qt 控件
- `standard_export.py` / `annotation_store.py` — pathlib 通用
- 测试套件 — 不依赖 GUI 与打包路径

---

## 4. Windows 打包方案

### 4.1 `robolabel-win.spec`（新建，onedir）

```python
# -*- mode: python ; coding: utf-8 -*-
# Windows 打包配置：onedir（dist/robolabel/robolabel.exe）
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
    exclude_binaries=True,           # onedir：exe 与依赖分目录放置
    name="robolabel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                   # windowed：双击不弹控制台
    disable_windowed_traceback=False,
    # argv_emulation 是 macOS 专属，Windows 删除
    icon=str(ROOT / "assets" / "app.ico"),   # ← 新增 Windows 图标
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
```

**onedir 而非 onefile 的理由**（与 macOS 文档结论一致）：

- onefile 每次启动解压全部依赖到 `%TEMP%`，冷启动慢数秒
- onefile 是杀软误报重灾区（无签名单文件 PE）；onedir 结构更易被白名单
- 后续内嵌 ffmpeg（方案 B）直接把 exe 放进 `dist/robolabel/bin/`，无需改代码

### 4.2 图标 `assets/app.ico`

用 Pillow 从 1024×1024 源 PNG 生成多尺寸 ICO（Windows 资源管理器需含 256px 大图标）：

```python
# scripts/make_ico.py（临时工具，或一次性脚本）
from PIL import Image
img = Image.open("assets/app_1024.png")
img.save("assets/app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
```

> 若暂无可用的设计图，先用 macOS 版同款占位图生成 `.ico` 打通打包链路（里程碑 M1），后续替换。
> 注意：Pillow 仅构建时需要，不进 `requirements.txt`（或放入单独 `requirements-build.txt`）。

### 4.3 构建脚本 `scripts/build_windows.ps1`

```powershell
# 构建 Windows onedir。产物: dist/robolabel/robolabel.exe
# 用法: powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$py = "python"   # 或 "py -3.12"
$venv = "build-venv-win"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    & $py -m venv $venv
    & "$venv\Scripts\python.exe" -m pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
}

& "$venv\Scripts\python.exe" -m PyInstaller robolabel-win.spec --clean --noconfirm

# 可选方案 B：内嵌 ffmpeg（见 4.4）
# New-Item -ItemType Directory -Force dist\robolabel\bin | Out-Null
# Copy-Item (Get-Command ffmpeg.exe).Source dist\robolabel\bin\
# Copy-Item (Get-Command ffprobe.exe).Source dist\robolabel\bin\

Write-Host "完成: dist\robolabel\robolabel.exe"
```

**双击冒烟测试清单（验收用）**：

1. 资源管理器中双击 `robolabel.exe`，确认窗口出现、无控制台
2. 确认任务管理器进程无残留
3. 系统缩放 125%/150% 下查看文字清晰度
4. 打开 H.265 / 高编码视频样本 → ffmpeg 兜底正常播放
5. 完整走一遍：打开数据集 → 场景标注 → 片段标注 → 保存 → 导出标准 JSON
6. 卸载 ffmpeg（临时改 PATH）→ 出现中文提示而非静默失败
7. `python -m pytest tests` 全绿
8. 拷贝 `dist/robolabel/` 到**另一台无 Python 环境的 Windows 机器**运行（验证依赖完备）

### 4.4 ffmpeg 兜底策略（二选一，默认 A）

- **方案 A（默认，本期必做）**：Windows 上 `winget install Gyan.FFmpeg`（或 choco/scoop），PATH 全局生效，Explorer 启动的 GUI 进程自动继承 → `shutil.which("ffmpeg")` 直接命中。缺失时按 3.2 给出中文提示。
- **方案 B（可选增强）**：把 `ffmpeg.exe` / `ffprobe.exe` 拷进 `dist/robolabel/bin/`，`video_decode.py` 优先探测 `resource_path("bin/ffmpeg.exe")` 再回退 PATH。注意 Gyan.FFmpeg 构建含 GPL 组件（x264 等），**对外分发需先做许可证评估**（可改用 LGPL 构建或仅内部使用）。与 macOS 文档的"方案 B"一致。

### 4.5 SmartScreen 与签名（按分发场景分层）

| 场景 | 做法 | 双击效果 |
| --- | --- | --- |
| 本机构建、本机使用 | 不签名 | ✅ 直接双击可用 |
| 局域网/组织内分发 | 自建代码签名证书（`signtool sign /f my.pfx`）+ 用户信任证书；或引导用户点"更多信息 → 仍要运行" | ⚠️ 首次 SmartScreen 弹窗 |
| 公网分发（推荐目标） | EV/OV 代码签名证书（`signtool sign` + 时间戳），Windows 10+ 内置信任 | ✅ 直接双击可用 |

> Windows 没有 macOS Gatekeeper 的 quarantine 机制；未签名的 PyInstaller 产物因"未知发布者"触发 SmartScreen，本机构建产物不会（本地创建的文件无 MOTW 标记）。拷贝到其他机器会弹窗，属预期行为，文档注明即可。

### 4.6 测试与回归

- 现有 `tests/` 不依赖 GUI 与打包路径，**不受影响**，预期全绿
- 新增小测试（放 `tests/test_platform.py`）：
  - `setup_logging` 在 `sys.platform != darwin` 时写 `%LOCALAPPDATA%`（mock 平台变量）
  - `ensure_macos_tool_path`（或重命名后）在非 darwin 平台下不修改 PATH
- 打包产物验证放手工冒烟清单

---

## 5. 里程碑与排期

| 里程碑 | 内容 | 涉及文件 | 估时 |
| --- | --- | --- | --- |
| **M1 出包** | `robolabel-win.spec` + `assets/app.ico` + `scripts/build_windows.ps1`，产出可双击 exe | `robolabel-win.spec`、`assets/`、`scripts/` | 0.5 天 |
| **M2 运行适配** | `app.py` 平台守卫 + 日志路径；`video_decode.py` 提示平台化；新增平台测试 | `lite_annotator/app.py`、`video_decode.py`、`tests/` | 0.5 天 |
| **M3 分发强化** | ffmpeg 内嵌（方案 B，含许可评估）；正式图标；README 补 Windows 章节 | `assets/app.ico`、`video_decode.py`、`README.md` | 1 天 |
| **M4 验收发布** | 双击冒烟全清单（含无 Python 环境机器）；pytest 回归；分发文档 | `README.md`、`docs/` | 0.5 天 |

**M1 + M2 完成后即达成核心目标**（Windows 双击可用），M3/M4 为分发体验增强。

---

## 6. 风险与回退

| 风险 | 说明 | 应对 |
| --- | --- | --- |
| SmartScreen 弹窗 | 未签名 exe 拷到其他机器提示"未知发布者" | 本机使用无影响；分发走签名（4.5），README 注明"更多信息 → 仍要运行" |
| 杀软误报 | PyInstaller 产物偶被 Defender/360 误报 | 用 onedir（非 onefile）；必要时提交加白名单；文档注明 |
| PyQt5 wheel 上限 | 官方 wheel 不支持 Python > 3.13 | 维持 Python ≤ 3.13（README 已有说明） |
| ffmpeg 内嵌的 GPL 许可 | Gyan 构建含 GPL 组件 | 默认方案 A（提示安装）；方案 B 仅许可评估通过后启用 |
| 非 ASCII 构建路径 | PyInstaller 对中文路径支持有限（历史问题） | 构建机项目路径使用纯 ASCII；文档强调 |
| 中文/空格数据集路径 | 数据集在含中文路径下打开 | `pathlib` 全程使用，正常支持；冒烟清单覆盖 |
| 无 Python 环境机器 | 用户机器无 Python | onedir 产物自带解释器，不依赖系统 Python（冒烟清单第 8 项验证） |
| 回退 | 新 spec 出问题 | 复用 `robolabel-onefile.spec` 改 `console=False` + `.ico` 即可单文件回退 |

---

## 7. 附录：Windows 开发环境准备（供开发/测试机）

```powershell
# 1. 安装 Python 3.9–3.13（python.org 安装包，勾选 "Add python.exe to PATH"）
# 2. 安装 ffmpeg（方案 A）
winget install Gyan.FFmpeg
#    安装后新开的终端才生效：ffmpeg -version 验证

# 3. 从源码运行
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m lite_annotator.app

# 4. 运行测试
pip install pytest
python -m pytest tests

# 5. 打包（M1 后）
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

---

## 8. 附：当前项目结构（Windows 涉及的路径）

```
robolabel/
├── robolabel.spec                 # macOS（不动）
├── robolabel-win.spec             # ← M1 新建：Windows onedir
├── lite_annotator/
│   ├── app.py                     # ← M2 平台守卫 + 日志路径
│   └── video_decode.py            # ← M2 ffmpeg 提示平台化
├── assets/app.ico                 # ← M1/M3 新增 Windows 图标
├── scripts/build_windows.ps1      # ← M1 新建
├── tests/test_platform.py         # ← M2 新增
├── README.md                      # ← M3 Windows 章节
└── docs/windows-packaging-plan.md # 本文档
```

---

## 9. 实施记录（M1–M2 已完成，2026-08-14）

| # | 计划原文 | 实际做法 | 原因 |
| --- | --- | --- | --- |
| 1 | `ensure_macos_tool_path` 改名 | **保留原函数名**，函数体加 `if sys.platform != "darwin": return` | 改动最小；`tests/test_paths.py:23` 已有 macOS 场景测试直接复用 |
| 2 | 日志路径直接在 `setup_logging` 内平台分支 | 抽出 `default_log_dir()` helper，`setup_logging` 只负责 mkdir + basicConfig | 平台路径可单测，避免触碰全局 logging 状态 |
| 3 | 新增 `tests/test_platform.py` | 6 个用例，其中 Windows 场景用 `monkeypatch.setattr(sys, "platform", ...)` 模拟 | 本机是 macOS，无法真机验证；注意 pathlib 在 POSIX 上分隔符为 `/`，断言不比对完整路径字符串 |
| 4 | Windows 无 `%LOCALAPPDATA%` 时回退 `~/.robolabel` | 同计划 | 面向精简环境兜底 |
| 5 | `make_ico.py` 从源 PNG 生成 | 从 `app.icns` 内直接提取最大 PNG（stdlib 解析 icns 分块），再经 Pillow 缩放存 7 尺寸 `.ico` | 仓库没有源 PNG，icns 内嵌 1024px PNG 即为唯一源图；零额外维护 |
| 6 | 无 Python 环境验证 | 本机为 macOS，无法执行 `build_windows.ps1` 与 Windows 双击冒烟 | 待 Windows 机器上执行（见下方待办） |

**验证结果**（macOS 本机）：

- `python -m pytest tests`：**59 passed**（新增 test_platform.py 6 例）
- `robolabel-win.spec` / `scripts/make_ico.py` 语法检查通过
- `assets/app.ico` 已生成（16/24/32/48/64/128/256 七尺寸，18KB）
- **Wine 交叉构建成功**（2026-08-14）：本机无 Windows 环境，用 Gcenx 便携 Wine 11.15（Rosetta）+ Windows Python 3.12.10 embeddable 执行 `PyInstaller robolabel-win.spec`，产出 `dist/robolabel/`（234MB onedir）+ `dist/robolabel-windows.zip`（89MB）；`robolabel.exe` 为 PE32+ GUI x86-64，Wine 下启动冒烟 12s 存活（Qt GUI 事件循环正常）

**待办（需 Windows 真机）**：双击冒烟全清单（§4.3）→ 无 Python 环境机器验证。注意：未签名 exe 首次运行 SmartScreen 需"更多信息 → 仍要运行"；ffmpeg 兜底需 `winget install Gyan.FFmpeg`。M3（ffmpeg 内嵌方案 B、README Windows 章节、正式图标）与 M4 未开始。
