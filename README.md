# robolabel

轻量级 RoboInter 风格的机器人操作视频标注工具（PyQt5 桌面应用），用于对 LeRobot 2.1 / CoRobot 数据集的机器人任务视频进行结构化标注。

## 功能特性

- **多相机视频播放**：最多 3 路相机共用同一时间轴，subtask 时间条 + phase 信息面板
- **场景标注**：任务类型、空间（场景词表带自动补全）、物品（名称 / 颜色 / 材质 / affordance）
- **片段（subtask）标注**：帧区间、状态（normal / abnormal）、片段技能、双手协调模式
- **细粒度 phase 标注**：每个 subtask 内可细分 approach / grasp / lift / release 等阶段
- **数据集级技能库**：可复用、可增删的片段技能模板库
- **严格 schema 校验**：帧区间必须无缝拼接覆盖整个视频，模板文本一致性校验，错误提示为中文
- **标准格式导入导出**：与 `annotation_schema_v1.json` 双向转换，支持 human / hybrid 标注来源标记
- **中英双语界面**，支持 HiDPI 缩放（可通过 `ROBOLABEL_UI_SCALE` 调整）
- **命令行迁移工具**：`tools/` 下历史标注导入与区间格式转换

## 环境要求

- Python 3.9 – 3.13（PyQt5 官方 wheel 不再支持更新的 Python 版本）
- `ffmpeg` / `ffprobe` 并在 PATH 中（OpenCV 无法解码的部分编码需要回退到 ffmpeg 解码）

macOS 安装 ffmpeg：

```bash
brew install ffmpeg
```

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 从源码运行

```bash
python -m lite_annotator.app
```

可选：调整界面缩放：

```bash
ROBOLABEL_UI_SCALE=1.2 python -m lite_annotator.app
```

## 运行测试

```bash
python -m pytest tests
```

## 打包可执行文件（macOS .app）

```bash
./scripts/build_macos.sh
```

生成产物：

```text
dist/robolabel.app
```

构建脚本会自动对产物做 ad-hoc 签名（`codesign --force --deep -s -`），本机双击即可打开界面。拷贝到其他 macOS 机器仍可能触发 Gatekeeper 拦截（未公证），首次需右键 → "打开"；公网分发建议用 Developer ID 签名 + `notarytool` 公证，详见 `docs/macos-packaging-plan.md`。其他平台请在目标平台构建。

## 项目结构

```
robolabel/
├── lite_annotator/      # 主应用（PyQt5 GUI）
├── common/              # 核心数据模型与校验（无 GUI 依赖）
│   └── skill_schema.py  # 标注 schema、模板渲染、校验逻辑
├── config/              # 标注模板与词表
├── tests/               # pytest 测试（校验、导出、编辑器等）
├── tools/               # 命令行迁移工具
├── requirements.txt     # 依赖清单
└── robolabel.spec       # PyInstaller 打包配置
```

### `lite_annotator/` — GUI 层

| 文件 | 职责 |
| --- | --- |
| `app.py` / `main_window.py` | 入口 + 主窗口，三栏布局：视频播放器 / 数据条目列表 + subtask 编辑器 / 任务描述 + 场景表单 + 技能库 |
| `multi_video_player.py` | 多相机视频播放器（最多 3 路共用时间轴），带 subtask 时间条和 phase 信息面板 |
| `video_player.py` / `video_decode.py` | 单相机播放器；OpenCV 帧读取，失败自动回退到 ffmpeg 解码 |
| `segment_editor.py` | subtask 编辑器：帧范围、状态（normal/abnormal）、技能选择、phase 标注对话框 |
| `scene_form.py` | 场景表单：任务类型、空间、机器人形态（单/双臂、末端类型）、物品增删（颜色/材质/affordance） |
| `skill_form.py` / `skill_template_dialog.py` | 技能填写表单（按场景物体、枚举约束生成控件，含实时文本预览）；主动作 + 辅助动作 + 协调方式 |
| `skill_library.py` | 数据集级技能库（`lite_annotations/skill_descriptions.json`）增删改 |
| `standard_export.py` | 与标准 `annotation_schema_v1.json` 双向转换（含去重、技能注册表、human/hybrid 标注来源标记） |
| `annotation_model.py` / `annotation_store.py` | 标注数据模型 + JSON bundle 读写（`annotations.json`） |
| `dataset_loader.py` | 数据集探测（LeRobot 2.1 vs CoRobot）、相机 / episode 枚举 |
| `vocabulary.py` / `object_attributes.py` / `ui_text.py` / `ui_theme.py` | 词表、物体引用、中英双语 UI 文本、主题样式（支持 HiDPI 缩放） |

### `common/skill_schema.py` — 核心约定

定义标注 schema（`skill_text_v1`）：

- **Annotation** = 任务描述 + 场景（scene）+ 机器人配置（robot_setup）+ 一串 **subtask**
- **Subtask** = 帧区间 [start, end)（半开区间）+ 协调模式 + 1~2 个 action + 可选的 phase 序列，要求首尾无缝拼接覆盖整个视频
- **Action** = subject（左/右末端等）+ skill + slots + 模板渲染出的 text
- **Phase** = 细粒度阶段（approach / grasp / lift / release 等规定动作）
- 自带完整校验：未知字段、枚举约束、模板文本一致性、连续性约束等，错误提示均为中文

### `config/` — 模板与词表

| 文件 | 内容 |
| --- | --- |
| `skill_templates.yaml` | 几十个技能定义（pick / place / pour 等），含槽位、枚举、phase 允许动作 |
| `coordination_modes.yaml` | 6 种双手协调模式（单手、双手同技能、主辅手等） |
| `scene_templates.yaml` | 场景文本模板 + 12 类任务 + 23 种 affordance |
| `lite_vocabulary.json` | 场景空间 / 物体名词典（源自 RoboCoin Viewer） |
| `phase_actions.json` / `skill_object_slots.json` | phase 动作表与物体槽位 |

### `tools/` — 数据迁移工具

- `import_legacy_human_annotations.py`：把历史人工标注导入为标准格式
- `convert_closed_intervals_to_half_open.py`：闭区间标注批量转半开区间（转换前自动备份）

## 标注工作流

1. **打开数据集** → 自动识别 LeRobot / CoRobot 布局，选择 1~3 个相机并指定主相机
2. **场景标注** → 填任务描述、任务类型、空间，添加物品（名称 / 颜色 / 材质 / affordance）
3. **技能片段标注** → 先建片段技能模板存入技能库 → 播放视频设起止帧 → 选择技能 / 协调模式 → 可选做 phase 级细分
4. **校验 / 保存 / 导出** → 实时校验（帧区间连续性、模板一致性等），通过后保存并导出标准格式 JSON，人工确认后标注来源标记为 human / hybrid