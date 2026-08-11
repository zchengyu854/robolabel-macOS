from __future__ import annotations

import json
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lite_annotator.annotation_model import (
    create_empty_annotation,
    validate_lite_annotation,
)
from lite_annotator.annotation_store import (
    default_annotation_dir,
    load_annotated_episode_keys,
    load_annotation_bundle,
    load_annotation_from_bundle,
    load_shared_task_fields,
    save_annotation_to_bundle,
    save_shared_task_fields,
)
from lite_annotator.dataset_loader import (
    DatasetType,
    EpisodeItem,
    detect_dataset_type,
    list_cameras,
    list_episodes,
)
from lite_annotator.multi_video_player import MultiCameraVideoPlayer
from lite_annotator.object_attributes import object_name, object_ref_text
from lite_annotator.scene_form import SceneForm
from lite_annotator.segment_editor import load_phase_actions
from lite_annotator.segment_editor import SegmentEditor
from lite_annotator.standard_export import (
    annotation_from_standard_episode,
    episode_annotation_source_text,
    find_standard_episode,
    mark_annotation_human_reviewed,
    read_standard_task_file,
    standard_annotation_path,
    standard_episode_is_annotated,
    to_standard_task_annotation,
)
from lite_annotator.skill_library import (
    add_skill_template,
    delete_skill_template,
    load_skill_library,
    skill_display_text,
)
from lite_annotator.skill_form import OBJECT_SLOT_KEYS
from lite_annotator.skill_template_dialog import SkillTemplateDialog
from lite_annotator.ui_text import bilingual_label
from lite_annotator.ui_theme import APP_NAME


class CameraSelectionDialog(QDialog):
    def __init__(self, cameras: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(bilingual_label("选择相机", "select cameras"))
        self.selected_cameras: list[str] = []
        self.main_camera: str | None = None

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.MultiSelection)
        for camera in cameras:
            item = QListWidgetItem(camera)
            self.list_widget.addItem(item)
        for index in range(min(3, self.list_widget.count())):
            self.list_widget.item(index).setSelected(True)

        self.main_camera_combo = QComboBox()
        self.list_widget.itemSelectionChanged.connect(self.refresh_main_camera_options)
        self.message = QLabel(bilingual_label("选择1到3个相机，共用同一时间轴", "select 1 to 3 cameras"))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.message)
        layout.addWidget(self.list_widget)
        layout.addWidget(QLabel(bilingual_label("主摄像头", "main camera")))
        layout.addWidget(self.main_camera_combo)
        layout.addWidget(buttons)
        self.refresh_main_camera_options()

    def selected_camera_names(self):
        return [item.text() for item in self.list_widget.selectedItems()]

    def refresh_main_camera_options(self):
        selected = self.selected_camera_names()
        current = self.main_camera_combo.currentText()
        self.main_camera_combo.blockSignals(True)
        self.main_camera_combo.clear()
        self.main_camera_combo.addItems(selected)
        if current in selected:
            self.main_camera_combo.setCurrentText(current)
        self.main_camera_combo.blockSignals(False)

    def accept(self):
        selected = self.selected_camera_names()
        if not selected:
            self.message.setText(bilingual_label("至少选择一个相机", "select at least one camera"))
            return
        if len(selected) > 3:
            self.message.setText("最多选择 3 个相机。")
            return
        main_camera = self.main_camera_combo.currentText()
        if main_camera not in selected:
            self.message.setText(bilingual_label("主摄像头必须在已选择相机中", "main camera must be selected"))
            return
        self.selected_cameras = selected
        self.main_camera = main_camera
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.dataset_root: Path | None = None
        self.dataset_type = DatasetType.UNKNOWN
        self.annotation_dir: Path | None = None
        self.episodes: list[EpisodeItem] = []
        self.selected_cameras: list[str] = []
        self.main_camera: str | None = None
        self.current_episode: EpisodeItem | None = None
        self.current_video_path: Path | None = None
        self.current_annotation_stem: str | None = None
        self.annotation = None
        self.skill_library = {"version": 1, "skills": []}
        self.loading_episode = False

        self.video_list = QTableWidget()
        self.video_list.setColumnCount(3)
        self.video_list.setHorizontalHeaderLabels([
            bilingual_label("状态", "status"),
            bilingual_label("来源", "source"),
            bilingual_label("数据条目", "episode"),
        ])
        self.video_list.verticalHeader().setVisible(False)
        self.video_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.video_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.video_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.video_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.video_list.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.video_list.horizontalHeader().setStretchLastSection(False)
        self.video_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.video_list.setColumnWidth(0, 100)
        self.video_list.setColumnWidth(1, 130)
        self.video_list.setColumnWidth(2, 420)
        self.video_list.currentCellChanged.connect(self.load_selected_episode)
        self.video_player = MultiCameraVideoPlayer()
        self.segment_editor = SegmentEditor()
        self.segment_editor.bind_frame_source(lambda: self.video_player.current_frame)
        self.segment_editor.segment_selected.connect(self.load_segment_into_form)
        self.segment_editor.subtask_added.connect(self.show_added_subtask_message)
        self.segment_editor.subtask_updated.connect(self.show_updated_subtask_message)
        self.segment_editor.subtask_deleted.connect(self.show_deleted_subtask_message)
        self.video_player.frame_changed.connect(self.segment_editor.set_current_frame)
        self.video_player.episode_loaded.connect(self.segment_editor.set_frame_count)

        self.video_text = QTextEdit()
        self.video_text.setPlaceholderText(bilingual_label("任务/视频描述", "task/video description"))
        self.video_text.setMaximumHeight(90)
        self.video_text.textChanged.connect(self.save_draft_annotation)
        self.scene_form = SceneForm()
        self.scene_form.scene_changed.connect(self.save_draft_annotation)
        self.scene_form.scene_changed.connect(self.sync_phase_object_options)
        self.skill_library_list = QListWidget()
        self.add_skill_template_button = QPushButton(bilingual_label("新增片段技能", "add segment skill"))
        self.add_skill_template_button.clicked.connect(self.add_current_skill_to_library)
        self.delete_skill_template_button = QPushButton(bilingual_label("删除片段技能", "delete segment skill"))
        self.delete_skill_template_button.clicked.connect(self.delete_selected_skill_template)
        self.validation_messages = QTextEdit()
        self.validation_messages.setReadOnly(True)
        self.validation_messages.setMaximumHeight(100)

        open_videos = QPushButton(bilingual_label("打开数据集", "open dataset"))
        open_videos.clicked.connect(self.choose_dataset_dir)
        save_button = QPushButton(bilingual_label("保存标注", "save annotations"))
        save_button.clicked.connect(self.save_current_annotation)
        export_json_button = QPushButton(bilingual_label("导出JSON", "export json"))
        export_json_button.clicked.connect(self.export_current_json)
        validate_button = QPushButton(bilingual_label("检查", "validate"))
        validate_button.clicked.connect(self.validate_current_annotation)

        toolbar = QHBoxLayout()
        toolbar.addWidget(open_videos)
        toolbar.addWidget(save_button)
        toolbar.addWidget(export_json_button)
        toolbar.addWidget(validate_button)

        left = QVBoxLayout()
        left.addWidget(self.video_player)

        middle = QVBoxLayout()
        middle.addWidget(QLabel(bilingual_label("数据条目", "episodes")))
        middle.addWidget(self.video_list)
        middle.addWidget(self.segment_editor)

        right = QVBoxLayout()
        right.addWidget(QLabel(bilingual_label("任务描述", "task description")))
        right.addWidget(self.video_text)
        right.addWidget(QLabel(bilingual_label("场景", "scene")))
        right.addWidget(self.scene_form)
        right.addWidget(QLabel(bilingual_label("片段技能展示", "segment skill display")))
        right.addWidget(self.skill_library_list)
        skill_library_buttons = QHBoxLayout()
        skill_library_buttons.addWidget(self.add_skill_template_button)
        skill_library_buttons.addWidget(self.delete_skill_template_button)
        right.addLayout(skill_library_buttons)
        right.addWidget(QLabel(bilingual_label("检查结果", "validation")))
        right.addWidget(self.validation_messages)

        content = QHBoxLayout()
        content.addLayout(left, 0)
        content.addLayout(middle, 2)
        content.addLayout(right, 3)

        root = QVBoxLayout()
        root.addLayout(toolbar)
        root.addLayout(content)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

    def choose_dataset_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Choose LeRobot/CoRobot dataset folder")
        if not path:
            return

        root = Path(path)
        dataset_type = detect_dataset_type(root)
        if dataset_type == DatasetType.UNKNOWN:
            QMessageBox.warning(
                self,
                "Unsupported dataset",
                "Could not detect LeRobot 2.1 or CoRobot layout.",
            )
            return

        cameras = list_cameras(root)
        if not cameras:
            QMessageBox.warning(self, "No cameras", "No camera video folders found.")
            return

        dialog = CameraSelectionDialog(cameras, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        self.save_draft_annotation()
        self.dataset_root = root
        self.dataset_type = dataset_type
        self.selected_cameras = dialog.selected_cameras
        self.main_camera = dialog.main_camera
        self.reset_current_annotation_state()
        self.load_skill_templates_for_dataset()
        self.refresh_episode_list()

    def reset_current_annotation_state(self):
        self.loading_episode = True
        try:
            self.current_episode = None
            self.current_video_path = None
            self.current_annotation_stem = None
            self.annotation = None
            self.skill_library = {"version": 1, "skills": []}
            self.skill_library_list.clear()
            self.segment_editor.set_skill_items([])
            self.segment_editor.set_segments([])
            self.segment_editor.set_scene_objects({})
            self.video_player.reset_episode()
            self.video_player.set_subtasks([])
            self.video_text.clear()
            self.scene_form.blockSignals(True)
            try:
                self.scene_form.clear()
            finally:
                self.scene_form.blockSignals(False)
            self.scene_form.set_referenced_objects(set())
            self.validation_messages.clear()
        finally:
            self.loading_episode = False

    def load_skill_templates_for_dataset(self):
        if not self.dataset_root:
            self.skill_library = {"version": 1, "skills": []}
        else:
            self.skill_library = load_skill_library(self.dataset_root)
        self.refresh_skill_library_list()

    def refresh_skill_library_list(self):
        self.skill_library_list.clear()
        for index, item in enumerate(self.skill_library.get("skills", []), start=1):
            label = skill_display_text(item)
            list_item = QListWidgetItem(f"{index}. {label}")
            list_item.setData(Qt.UserRole, item)
            self.skill_library_list.addItem(list_item)
        self.segment_editor.set_skill_items(self.skill_library.get("skills", []))
        self.update_scene_object_references()

    def active_annotation_dir(self, episode: EpisodeItem | None = None) -> Path | None:
        if self.annotation_dir:
            return self.annotation_dir
        if self.dataset_root:
            return default_annotation_dir(self.dataset_root)
        return None

    def active_annotation_stem(self, episode: EpisodeItem | None = None) -> str | None:
        episode = episode or self.current_episode
        if episode:
            return episode.annotation_stem
        return self.current_annotation_stem

    def active_annotation_file(self) -> Path | None:
        annotation_dir = self.active_annotation_dir()
        return annotation_dir / "annotations.json" if annotation_dir else None

    def refresh_episode_list(self):
        self.video_list.blockSignals(True)
        self.video_list.setRowCount(0)
        if not self.dataset_root:
            self.video_list.blockSignals(False)
            return
        try:
            self.episodes = list_episodes(self.dataset_root, self.selected_cameras)
        except Exception as exc:
            self.video_list.blockSignals(False)
            QMessageBox.warning(self, "Dataset load failed", str(exc))
            return
        annotated_keys = set()
        annotation_bundle = {}
        annotation_file = self.active_annotation_file()
        if annotation_file:
            annotated_keys = set(load_annotated_episode_keys(annotation_file))
            annotation_bundle = load_annotation_bundle(annotation_file)
        standard_annotation = {}
        if self.dataset_root:
            standard_annotation = read_standard_task_file(standard_annotation_path(self.dataset_root))
        for episode in self.episodes:
            standard_episode = find_standard_episode(
                standard_annotation,
                episode,
                episode.camera_videos.get(self.main_camera) or episode.primary_video_path,
            ) if standard_annotation else None
            annotated = (
                episode.annotation_stem in annotated_keys
                or standard_episode_is_annotated(standard_episode)
            )
            source_text = self.episode_source_text(
                episode,
                standard_episode,
                annotation_bundle,
            )
            row = self.video_list.rowCount()
            self.video_list.insertRow(row)
            status_item = QTableWidgetItem(
                self.episode_status_text(annotated)
            )
            source_item = QTableWidgetItem(source_text)
            episode_item = QTableWidgetItem(episode.display_name)
            status_item.setData(Qt.UserRole, episode)
            source_item.setData(Qt.UserRole, episode)
            episode_item.setData(Qt.UserRole, episode)
            self.video_list.setItem(row, 0, status_item)
            self.video_list.setItem(row, 1, source_item)
            self.video_list.setItem(row, 2, episode_item)
        self.video_list.resizeColumnToContents(2)
        if self.video_list.columnWidth(2) < 420:
            self.video_list.setColumnWidth(2, 420)
        self.video_list.blockSignals(False)
        self.validation_messages.setText(
            f"Loaded {self.dataset_type.value}: {len(self.episodes)} episodes, "
            f"{len(self.selected_cameras)} cameras, "
            f"{len(annotated_keys)} annotations"
        )

    def episode_status_text(self, annotated: bool) -> str:
        return bilingual_label("已标注", "annotated") if annotated else ""

    def bundle_episode_source_text(self, annotation_bundle: dict, annotation_stem: str) -> str:
        annotation = (annotation_bundle.get("annotations") or {}).get(annotation_stem)
        if not isinstance(annotation, dict) or not annotation.get("subtasks"):
            return ""
        return episode_annotation_source_text({
            "annotation_meta": annotation.get("annotation_meta") or {"source": "human"},
            "subtasks": annotation.get("subtasks"),
        })

    def episode_source_text(
        self,
        episode: EpisodeItem,
        standard_episode: dict | None,
        annotation_bundle: dict,
    ) -> str:
        source_text = episode_annotation_source_text(standard_episode)
        if source_text:
            return source_text
        return self.bundle_episode_source_text(annotation_bundle, episode.annotation_stem)

    def episode_from_row(self, row: int) -> EpisodeItem | None:
        if row < 0:
            return None
        item = self.video_list.item(row, 2) or self.video_list.item(row, 1) or self.video_list.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def refresh_current_episode_label(self):
        if not self.current_episode:
            return
        row = self.video_list.currentRow()
        if row < 0 or self.episode_from_row(row) != self.current_episode:
            row = next(
                (
                    index
                    for index in range(self.video_list.rowCount())
                    if self.episode_from_row(index) == self.current_episode
                ),
                -1,
            )
        if row < 0:
            return
        annotation_file = self.active_annotation_file()
        annotated_keys = set(load_annotated_episode_keys(annotation_file)) if annotation_file else set()
        annotation_bundle = load_annotation_bundle(annotation_file) if annotation_file else {}
        standard_episode = None
        if self.dataset_root:
            standard_annotation = read_standard_task_file(standard_annotation_path(self.dataset_root))
            if standard_annotation:
                standard_episode = find_standard_episode(
                    standard_annotation,
                    self.current_episode,
                    self.current_video_path,
                )
        status_item = self.video_list.item(row, 0)
        if status_item is None:
            status_item = QTableWidgetItem()
            status_item.setData(Qt.UserRole, self.current_episode)
            self.video_list.setItem(row, 0, status_item)
        status_item.setText(
            self.episode_status_text(
                self.current_episode.annotation_stem in annotated_keys
                or standard_episode_is_annotated(standard_episode)
            )
        )
        source_item = self.video_list.item(row, 1)
        if source_item is None:
            source_item = QTableWidgetItem()
            source_item.setData(Qt.UserRole, self.current_episode)
            self.video_list.setItem(row, 1, source_item)
        source_item.setText(
            self.episode_source_text(
                self.current_episode,
                standard_episode,
                annotation_bundle,
            )
        )

    def load_selected_episode(self, current_row, current_column, previous_row, previous_column):
        episode = self.episode_from_row(current_row)
        if episode:
            self.load_episode(episode)

    def load_saved_annotation(self, annotation_stem: str):
        bundle_path = self.active_annotation_file()
        if bundle_path:
            bundle_annotation = load_annotation_from_bundle(bundle_path, annotation_stem)
            if bundle_annotation and bundle_annotation.get("subtasks"):
                return bundle_annotation
        if self.dataset_root and self.current_episode:
            standard_path = standard_annotation_path(self.dataset_root)
            standard_annotation = read_standard_task_file(standard_path)
            standard_episode = find_standard_episode(
                standard_annotation,
                self.current_episode,
                self.current_video_path,
            ) if standard_annotation else None
            if standard_episode_is_annotated(standard_episode):
                return annotation_from_standard_episode(
                    standard_annotation,
                    standard_episode,
                    self.build_episode_metadata(self.current_episode),
                )
        return None

    def apply_shared_task_fields(self, annotation):
        annotation_file = self.active_annotation_file()
        if not annotation_file:
            return annotation
        shared = load_shared_task_fields(annotation_file)
        if shared.get("video_text"):
            annotation["video_text"] = shared["video_text"]
        if shared.get("scene"):
            annotation["scene"] = shared["scene"]
        if shared.get("robot_setup"):
            annotation["robot_setup"] = shared["robot_setup"]
        return annotation

    def load_episode(self, episode: EpisodeItem):
        self.save_draft_annotation()
        self.current_episode = episode
        self.current_video_path = episode.camera_videos.get(self.main_camera) or episode.primary_video_path
        self.current_annotation_stem = episode.annotation_stem
        try:
            self.video_player.load_episode(episode.camera_videos, self.main_camera)
        except Exception as exc:
            QMessageBox.warning(self, "Episode load failed", str(exc))
            return

        annotation_stem = self.active_annotation_stem(episode)
        saved_annotation = self.load_saved_annotation(annotation_stem) if annotation_stem else None

        if saved_annotation:
            self.annotation = saved_annotation
        else:
            self.annotation = create_empty_annotation(
                self.current_video_path,
                self.video_player.frame_count,
            )
            self.annotation["episode"].update(self.build_episode_metadata(episode))
        self.annotation = self.apply_shared_task_fields(self.annotation)

        self.loading_episode = True
        try:
            self.video_text.setText(self.annotation.get("video_text", ""))
            self.scene_form.load_scene(self.annotation.get("scene"))
            self.scene_form.load_robot_setup(self.annotation.get("robot_setup"))
            self.sync_phase_object_options()
            self.segment_editor.set_segments(self.annotation.get("subtasks") or [])
            self.video_player.set_subtasks(self.current_subtasks())
            source_text = episode_annotation_source_text({
                "annotation_meta": self.annotation.get("annotation_meta") or {},
                "subtasks": self.annotation.get("subtasks") or [],
            })
            self.validation_messages.setText(
                f"当前标注来源: {source_text}" if source_text else ""
            )
        finally:
            self.loading_episode = False

    def build_episode_metadata(self, episode: EpisodeItem):
        views = {
            camera: str(path)
            for camera, path in episode.camera_videos.items()
        }
        primary_video_path = episode.camera_videos.get(self.main_camera) or episode.primary_video_path
        return {
            "episode_id": episode.episode_id,
            "task_id": episode.display_name,
            "dataset_name": episode.dataset_root.name,
            "video_path": str(primary_video_path),
            "primary_video_path": str(primary_video_path),
            "views": views,
            "frames": self.video_player.frame_count,
        }

    def load_segment_into_form(self, key):
        subtask = self.segment_editor.segments.get(key)
        if isinstance(subtask, dict):
            self.video_player.set_current_subtask(subtask)
            tail_frame = max(
                int(subtask.get("start_frame", key[0])),
                int(subtask.get("end_frame", key[1])) - 1,
            )
            self.video_player.seek(tail_frame)
            self.validation_messages.setText(subtask.get("text", ""))

    def sync_phase_object_options(self):
        object_options = self.scene_form.selected_object_options()
        self.segment_editor.set_scene_objects(object_options)
        object_display_labels = {
            object_ref_text(item): str(item.get("label", object_ref_text(item)))
            for item in object_options.values()
            if isinstance(item, dict) and object_ref_text(item)
        }
        self.video_player.set_display_label_maps(
            object_options=object_display_labels,
            action_options={value: label for value, label in load_phase_actions()},
        )
        self.update_scene_object_references()

    def referenced_objects_from_subtask(self, subtask):
        values = set()
        if not isinstance(subtask, dict):
            return values
        for action in subtask.get("actions") or []:
            if not isinstance(action, dict):
                continue
            slots = action.get("slots") or {}
            for key in OBJECT_SLOT_KEYS | {"source_anchor", "destination_anchor"}:
                raw_value = slots.get(key, "")
                value = object_ref_text(raw_value) if isinstance(raw_value, dict) else str(raw_value).strip()
                if value:
                    values.add(value)
                name = object_name(raw_value)
                if name:
                    values.add(name)
        for phase in subtask.get("phases") or []:
            if not isinstance(phase, dict):
                continue
            raw_value = phase.get("object", "")
            value = object_ref_text(raw_value) if isinstance(raw_value, dict) else str(raw_value).strip()
            if value:
                values.add(value)
            name = object_name(raw_value)
            if name:
                values.add(name)
        return values

    def referenced_scene_objects(self):
        values = set()
        for item in self.skill_library.get("skills", []):
            template = item.get("template") or {}
            values.update(self.referenced_objects_from_subtask(template))

        for subtask in self.segment_editor.segments.values():
            values.update(self.referenced_objects_from_subtask(subtask))

        annotation_file = self.active_annotation_file()
        if annotation_file:
            bundle = load_annotation_bundle(annotation_file)
            for annotation in bundle.get("annotations", {}).values():
                for subtask in annotation.get("subtasks", []):
                    values.update(self.referenced_objects_from_subtask(subtask))
        return values

    def update_scene_object_references(self):
        self.scene_form.set_referenced_objects(self.referenced_scene_objects())

    def current_skill_template(self):
        dialog = SkillTemplateDialog(
            self,
            scene_object_options=self.scene_form.selected_object_options(),
            robot_setup=self.scene_form.build_robot_setup(),
        )
        if dialog.exec_() != QDialog.Accepted:
            return None
        return dialog.build_template()

    def add_current_skill_to_library(self):
        if not self.dataset_root:
            self.validation_messages.setText("Open dataset first.")
            return
        try:
            template = self.current_skill_template()
        except Exception as exc:
            self.validation_messages.setText(str(exc))
            return
        if template is None:
            return
        item = add_skill_template(self.dataset_root, template)
        self.load_skill_templates_for_dataset()
        self.validation_messages.setText(f"Added segment skill: {item['text']}")

    def show_added_subtask_message(self, subtask):
        self.video_player.set_subtasks(self.current_subtasks())
        self.video_player.set_current_subtask(subtask)
        self.update_scene_object_references()
        self.save_draft_annotation()
        self.validation_messages.setText(f"Added subtask annotation: {subtask['text']}")

    def show_updated_subtask_message(self, subtask):
        self.video_player.set_subtasks(self.current_subtasks())
        self.video_player.set_current_subtask(subtask)
        self.update_scene_object_references()
        self.save_draft_annotation()
        self.validation_messages.setText(f"Updated subtask annotation: {subtask['text']}")

    def show_deleted_subtask_message(self, subtask):
        self.video_player.set_subtasks(self.current_subtasks())
        self.video_player.set_current_subtask(None)
        self.update_scene_object_references()
        self.save_draft_annotation()
        self.validation_messages.setText("Deleted subtask annotation.")

    def selected_skill_template_item(self):
        item = self.skill_library_list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def skill_is_bound_to_subtask(self, skill_id: str) -> bool:
        for subtask in self.segment_editor.segments.values():
            if isinstance(subtask, dict) and subtask.get("skill_id") == skill_id:
                return True

        annotation_file = self.active_annotation_file()
        if not annotation_file:
            return False
        bundle = load_annotation_bundle(annotation_file)
        for annotation in bundle.get("annotations", {}).values():
            for subtask in annotation.get("subtasks", []):
                if isinstance(subtask, dict) and subtask.get("skill_id") == skill_id:
                    return True
        return False

    def delete_selected_skill_template(self):
        if not self.dataset_root:
            return
        item = self.selected_skill_template_item()
        if item is None:
            self.validation_messages.setText("Select a segment skill first.")
            return
        if self.skill_is_bound_to_subtask(item["id"]):
            self.validation_messages.setText("该片段技能已绑定subtask，不能删除。")
            return
        delete_skill_template(self.dataset_root, item["id"])
        self.load_skill_templates_for_dataset()
        self.validation_messages.setText("Deleted segment skill.")

    def collect_annotation(self):
        if self.annotation is None or self.current_video_path is None:
            return None
        annotation = dict(self.annotation)
        annotation["video_text"] = self.video_text.toPlainText().strip()
        annotation["scene"] = self.scene_form.build_scene()
        annotation["robot_setup"] = self.scene_form.build_robot_setup()

        subtasks = []
        for key, value in sorted(self.segment_editor.segments.items()):
            if isinstance(value, dict):
                subtasks.append(value)
        annotation["subtasks"] = subtasks
        annotation["episode"]["frames"] = self.video_player.frame_count
        if self.current_episode is not None:
            annotation["episode"].update(self.build_episode_metadata(self.current_episode))
        return annotation

    def current_subtasks(self):
        return [
            value for key, value in sorted(self.segment_editor.segments.items())
            if isinstance(value, dict)
        ]

    def save_draft_annotation(self):
        if self.loading_episode:
            return
        annotation_file = self.active_annotation_file()
        annotation_stem = self.active_annotation_stem()
        if not annotation_file or not annotation_stem:
            return
        try:
            annotation = self.collect_annotation()
        except Exception:
            return
        if annotation is None:
            return
        self.persist_annotation(annotation_file, annotation_stem, annotation)
        self.annotation = annotation
        self.refresh_current_episode_label()

    def persist_annotation(self, annotation_file: Path, annotation_stem: str, annotation: dict):
        save_shared_task_fields(annotation_file, {
            "video_text": annotation.get("video_text", ""),
            "scene": annotation.get("scene"),
            "robot_setup": annotation.get("robot_setup"),
        })
        save_annotation_to_bundle(annotation_file, annotation_stem, annotation)

    def write_standard_annotation_file(self, annotation_file: Path) -> Path | None:
        if not self.dataset_root:
            return None
        bundle = load_annotation_bundle(annotation_file)
        export_path = standard_annotation_path(self.dataset_root)
        existing_standard = read_standard_task_file(export_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        primary_video_paths = {
            episode.annotation_stem: str(episode.camera_videos.get(self.main_camera) or episode.primary_video_path)
            for episode in self.episodes
        }
        standard_annotation = to_standard_task_annotation(
            bundle,
            dataset_type=self.dataset_type,
            dataset_root=self.dataset_root,
            primary_video_paths=primary_video_paths,
            episode_order=[episode.annotation_stem for episode in self.episodes],
            existing_standard=existing_standard,
        )
        export_path.write_text(
            json.dumps(standard_annotation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return export_path

    def validate_current_annotation(self):
        try:
            annotation = self.collect_annotation()
        except Exception as exc:
            self.validation_messages.setText(str(exc))
            return [str(exc)]
        if annotation is None:
            self.validation_messages.setText("No video loaded")
            return ["No video loaded"]
        errors = validate_lite_annotation(annotation, self.video_player.frame_count)
        self.validation_messages.setText("\n".join(errors) if errors else "OK")
        return errors

    def save_current_annotation(self):
        annotation_file = self.active_annotation_file()
        if not annotation_file:
            QMessageBox.warning(self, "Missing dataset", "Open a dataset first.")
            return
        try:
            annotation = self.collect_annotation()
        except Exception as exc:
            self.validation_messages.setText(str(exc))
            QMessageBox.warning(self, "Annotation error", str(exc))
            return
        if annotation is None:
            return
        errors = validate_lite_annotation(annotation, self.video_player.frame_count)
        if errors:
            self.validation_messages.setText("\n".join(errors))
            QMessageBox.warning(self, "Validation failed", "Fix validation errors before saving.")
            return
        annotation_stem = self.active_annotation_stem()
        mark_annotation_human_reviewed(annotation)
        self.persist_annotation(annotation_file, annotation_stem, annotation)
        export_path = self.write_standard_annotation_file(annotation_file)
        self.annotation = annotation
        self.refresh_current_episode_label()
        if export_path:
            self.validation_messages.setText(f"Saved: {annotation_file}\nUpdated: {export_path}")
        else:
            self.validation_messages.setText(f"Saved: {annotation_file}")

    def export_current_json(self):
        annotation_file = self.active_annotation_file()
        if not annotation_file:
            QMessageBox.warning(self, "Missing dataset", "Open a dataset first.")
            return
        try:
            annotation = self.collect_annotation()
        except Exception as exc:
            self.validation_messages.setText(str(exc))
            QMessageBox.warning(self, "Annotation error", str(exc))
            return
        if annotation is None:
            return
        annotation_stem = self.active_annotation_stem()
        mark_annotation_human_reviewed(annotation)
        self.persist_annotation(annotation_file, annotation_stem, annotation)
        export_path = self.write_standard_annotation_file(annotation_file)
        self.annotation = annotation
        self.refresh_current_episode_label()
        self.validation_messages.setText(f"Exported: {export_path}")
