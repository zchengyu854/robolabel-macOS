from __future__ import annotations

import json
from copy import deepcopy

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from common.skill_schema import load_skill_templates
from lite_annotator.object_attributes import object_ref_matches, object_ref_text
from lite_annotator.ui_text import bilingual_label
from lite_annotator.skill_library import skill_display_text
from lite_annotator.paths import resource_path

PHASE_ACTIONS_PATH = resource_path("config/phase_actions.json")
_, SKILL_TEMPLATES = load_skill_templates()


def load_phase_actions(path=PHASE_ACTIONS_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [
        (str(item["value"]), str(item.get("label", item["value"])))
        for item in data
    ]


class PhaseDialog(QDialog):
    def __init__(
        self,
        frame_count=0,
        current_frame=0,
        object_options=None,
        phases=None,
        allowed_actions=None,
        optional_actions=None,
        action_targets=None,
        subtask_start_frame=None,
        subtask_end_frame=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(bilingual_label("phase标注", "phase annotation"))
        self.phases = list(phases or [])
        self.allowed_actions = set(allowed_actions or [])
        self.optional_actions = set(optional_actions or [])
        self.action_targets = list(action_targets or [("primary", "主动作(primary)")])
        self.subtask_start_frame = subtask_start_frame
        self.subtask_end_frame = subtask_end_frame
        frame_count = max(int(frame_count), 0)
        max_start_frame = max(frame_count - 1, 0)
        max_end_frame = max(frame_count, 0)
        current_frame = max(0, min(int(current_frame), max_start_frame))

        self.phase_list_widget = QListWidget()
        self.phase_list_widget.currentItemChanged.connect(self.load_selected_phase)
        self.start_frame_input = QSpinBox()
        self.start_frame_input.setRange(0, max_start_frame)
        self.start_frame_input.setValue(current_frame)
        self.end_frame_input = QSpinBox()
        self.end_frame_input.setRange(0, max_end_frame)
        self.end_frame_input.setValue(min(current_frame + 1, max_end_frame))
        self.action_select = QComboBox()
        for value, label in load_phase_actions():
            if self.allowed_actions and value not in self.allowed_actions:
                continue
            optional_suffix = " - 可选(optional)" if value in self.optional_actions else ""
            self.action_select.addItem(f"{label}({value}){optional_suffix}", value)
        self.object_select = QComboBox()
        for _, item in (object_options or {}).items():
            if not isinstance(item, dict):
                continue
            value = {
                "name": str(item.get("name", "")).strip(),
                "color": str(item.get("color", "")).strip(),
                "material": str(item.get("material", "")).strip(),
            }
            if value["name"]:
                self.object_select.addItem(str(item.get("label", value["name"])), value)
        self.target_action_select = QComboBox()
        for value, label in self.action_targets:
            self.target_action_select.addItem(str(label), str(value))
        self.add_phase_button = QPushButton("新增")
        self.update_phase_button = QPushButton("修改")
        self.delete_phase_button = QPushButton("删除")
        self.add_phase_button.clicked.connect(self.add_phase_from_inputs)
        self.update_phase_button.clicked.connect(self.update_selected_phase)
        self.delete_phase_button.clicked.connect(self.delete_selected_phase)

        form = QFormLayout()
        form.addRow(bilingual_label("起始帧", "start frame"), self.start_frame_input)
        form.addRow(bilingual_label("结束帧(不含)", "end frame exclusive"), self.end_frame_input)
        form.addRow(bilingual_label("动作", "action"), self.action_select)
        form.addRow(bilingual_label("物品", "object"), self.object_select)
        form.addRow(bilingual_label("所属动作", "action owner"), self.target_action_select)

        phase_buttons = QHBoxLayout()
        phase_buttons.addWidget(self.add_phase_button)
        phase_buttons.addWidget(self.update_phase_button)
        phase_buttons.addWidget(self.delete_phase_button)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText(bilingual_label("确定", "ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(bilingual_label("取消", "cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        if self.subtask_start_frame is not None:
            start_text = str(int(self.subtask_start_frame))
            if self.subtask_end_frame is None:
                hint = f"当前subtask起始帧: {start_text}"
            else:
                hint = (
                    f"当前subtask范围: {int(self.subtask_start_frame)}:"
                    f"{int(self.subtask_end_frame)}，起始帧: {start_text}"
                )
            layout.addWidget(QLabel(hint))
        layout.addWidget(self.phase_list_widget)
        layout.addLayout(form)
        layout.addLayout(phase_buttons)
        layout.addWidget(buttons)
        self.refresh_phase_list()

    def build_phase(self):
        start = int(self.start_frame_input.value())
        end = int(self.end_frame_input.value())
        return {
            "start_frame": start,
            "end_frame": end,
            "action": str(self.action_select.currentData() or self.action_select.currentText()),
            "object": self.object_select.currentData() or self.object_select.currentText(),
            "target_action": str(self.target_action_select.currentData() or "primary"),
        }

    def refresh_phase_list(self):
        self.phase_list_widget.clear()
        for index, phase in enumerate(self.phases, start=1):
            item = QListWidgetItem(
                f"{index}. {int(phase['start_frame'])}:{int(phase['end_frame'])}  "
                f"{phase.get('target_action', 'primary')}  "
                f"{phase.get('action', '')}  {object_ref_text(phase.get('object', ''))}"
            )
            self.phase_list_widget.addItem(item)

    def add_phase_from_inputs(self):
        self.phases.append(self.build_phase())
        self.phases.sort(key=lambda item: (int(item["start_frame"]), int(item["end_frame"])))
        self.refresh_phase_list()

    def update_selected_phase(self):
        row = self.phase_list_widget.currentRow()
        if row < 0 or row >= len(self.phases):
            return
        self.phases[row] = self.build_phase()
        self.phases.sort(key=lambda item: (int(item["start_frame"]), int(item["end_frame"])))
        self.refresh_phase_list()

    def delete_selected_phase(self):
        row = self.phase_list_widget.currentRow()
        if row < 0 or row >= len(self.phases):
            return
        self.phases.pop(row)
        self.refresh_phase_list()

    def load_selected_phase(self, current, previous):
        row = self.phase_list_widget.currentRow()
        if row < 0 or row >= len(self.phases):
            return
        phase = self.phases[row]
        self.start_frame_input.setValue(int(phase.get("start_frame", 0)))
        self.end_frame_input.setValue(int(phase.get("end_frame", 0)))
        action_index = self.action_select.findData(phase.get("action"))
        if action_index >= 0:
            self.action_select.setCurrentIndex(action_index)
        for index in range(self.object_select.count()):
            item_data = self.object_select.itemData(index)
            if item_data == phase.get("object") or object_ref_matches(item_data, phase.get("object")):
                self.object_select.setCurrentIndex(index)
                break
        target_index = self.target_action_select.findData(phase.get("target_action", "primary"))
        if target_index >= 0:
            self.target_action_select.setCurrentIndex(target_index)


class SegmentEditor(QWidget):
    segment_selected = pyqtSignal(tuple)
    subtask_added = pyqtSignal(dict)
    subtask_updated = pyqtSignal(dict)
    subtask_deleted = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.segments = {}
        self.get_current_frame = lambda: 0
        self.has_bound_frame_source = False
        self.current_frame = 0
        self.skill_items = []
        self.scene_object_options = {}

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.emit_selected_segment)

        self.current_frame_label = QLabel(f"{bilingual_label('当前帧', 'current frame')}: -")
        self.message_label = QLabel("")
        self.start_frame_input = QSpinBox()
        self.start_frame_input.setRange(0, 0)
        self.end_frame_input = QSpinBox()
        self.end_frame_input.setRange(0, 0)
        self.skill_select = QComboBox()
        self.state_select = QComboBox()
        self.state_select.addItem("正常(normal)", "normal")
        self.state_select.addItem("异常(abnormal)", "abnormal")

        self.frame_controls_widget = QWidget()
        frame_controls = QHBoxLayout(self.frame_controls_widget)
        frame_controls.setContentsMargins(0, 0, 0, 0)
        self.use_current_as_start_button = QPushButton("设为起始帧")
        self.use_current_as_end_button = QPushButton("设为结束帧")
        self.use_current_as_start_button.clicked.connect(self.set_start_to_current_frame)
        self.use_current_as_end_button.clicked.connect(self.set_end_to_current_frame)
        frame_controls.addWidget(self.use_current_as_start_button)
        frame_controls.addWidget(self.use_current_as_end_button)

        self.add_button = QPushButton("新增subtask标注")
        self.update_button = QPushButton("更新")
        self.delete_button = QPushButton("删除")
        self.add_button.clicked.connect(self.add_subtask_from_inputs)
        self.update_button.clicked.connect(self.update_subtask_from_inputs)
        self.delete_button.clicked.connect(self.delete_selected)

        self.subtask_buttons_widget = QWidget()
        self.subtask_buttons_layout = QHBoxLayout(self.subtask_buttons_widget)
        self.subtask_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.subtask_buttons_layout.addWidget(self.add_button)
        self.subtask_buttons_layout.addWidget(self.update_button)
        self.subtask_buttons_layout.addWidget(self.delete_button)

        form = QFormLayout()
        form.addRow(bilingual_label("起始帧", "start frame"), self.start_frame_input)
        form.addRow(bilingual_label("结束帧(不含)", "end frame exclusive"), self.end_frame_input)
        form.addRow(bilingual_label("状态", "state"), self.state_select)
        form.addRow(bilingual_label("片段技能", "segment skill"), self.skill_select)

        self.phase_button = QPushButton("phase标注")
        self.phase_button.clicked.connect(self.open_phase_dialog)

        self.phase_controls_widget = QWidget()
        phase_buttons = QHBoxLayout(self.phase_controls_widget)
        phase_buttons.setContentsMargins(0, 0, 0, 0)
        phase_buttons.addWidget(self.phase_button)

        self.list_title_label = QLabel(bilingual_label("subtask标注", "subtask annotations"))
        layout = QVBoxLayout(self)
        layout.addWidget(self.list_title_label)
        layout.addWidget(self.current_frame_label)
        layout.addLayout(form)
        layout.addWidget(self.frame_controls_widget)
        layout.addWidget(self.subtask_buttons_widget)
        layout.addWidget(self.message_label)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.phase_controls_widget)

    def bind_frame_source(self, get_current_frame):
        self.get_current_frame = get_current_frame
        self.has_bound_frame_source = True

    def set_frame_count(self, frame_count):
        max_frame = max(int(frame_count) - 1, 0)
        self.start_frame_input.setRange(0, max_frame)
        self.end_frame_input.setRange(0, max_frame + 1)
        self.set_current_frame(min(self.current_frame, max_frame))

    def set_current_frame(self, frame):
        max_frame = max(self.start_frame_input.maximum(), 0)
        self.current_frame = max(0, min(int(frame), max_frame))
        self.current_frame_label.setText(
            f"{bilingual_label('当前帧', 'current frame')}: {self.current_frame}"
        )

    def sync_current_frame_from_source(self):
        if not self.has_bound_frame_source:
            return
        try:
            self.set_current_frame(self.get_current_frame())
        except Exception:
            pass

    def set_start_to_current_frame(self):
        self.sync_current_frame_from_source()
        self.start_frame_input.setValue(self.current_frame)

    def set_end_to_current_frame(self):
        self.sync_current_frame_from_source()
        self.end_frame_input.setValue(
            min(self.current_frame + 1, self.end_frame_input.maximum())
        )

    def set_scene_objects(self, object_options):
        self.scene_object_options = dict(object_options or {})

    def set_skill_items(self, skill_items):
        self.skill_items = skill_items
        self.skill_select.clear()
        for item in skill_items:
            label = skill_display_text(item)
            self.skill_select.addItem(label, item)
        self.add_button.setEnabled(bool(skill_items))
        self.update_button.setEnabled(bool(skill_items))

    def current_key(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def clear_subtask_form(self):
        self.start_frame_input.setValue(0)
        self.end_frame_input.setValue(0)
        state_index = self.state_select.findData("normal")
        if state_index >= 0:
            self.state_select.setCurrentIndex(state_index)
        self.skill_select.setCurrentIndex(-1)
        self.message_label.setText("")

    def set_segments(self, subtasks):
        self.segments = {
            (int(item["start_frame"]), int(item["end_frame"])): item
            for item in subtasks
        }
        self.refresh()
        if not self.segments:
            self.clear_subtask_form()

    def add_or_update_subtask(self, subtask):
        key = (int(subtask["start_frame"]), int(subtask["end_frame"]))
        self.segments[key] = subtask
        self.refresh(selected_key=key)

    def build_subtask_from_inputs(self):
        item = self.skill_select.currentData()
        if item is None:
            return None
        template = deepcopy(item.get("template") or {})
        start = int(self.start_frame_input.value())
        end = int(self.end_frame_input.value())
        return {
            "start_frame": start,
            "end_frame": end,
            "state": str(self.state_select.currentData() or "normal"),
            "skill_id": item.get("id", ""),
            "coordination_mode": template.get("coordination_mode", "single_hand"),
            "actions": template.get("actions") or [],
            "text": template.get("text", ""),
        }

    def skill_item_matches_subtask(self, item, subtask):
        if not isinstance(item, dict) or not isinstance(subtask, dict):
            return False
        skill_id = str(subtask.get("skill_id", "")).strip()
        if skill_id and item.get("id") == skill_id:
            return True

        template = item.get("template") or {}
        template_actions = template.get("actions") or []
        subtask_actions = subtask.get("actions") or []
        if template_actions and template_actions == subtask_actions:
            return True

        template_text = str(template.get("text") or item.get("text") or "").strip()
        subtask_text = str(subtask.get("text") or "").strip()
        return bool(template_text and subtask_text and template_text == subtask_text)

    def action_skill_sequence(self, actions):
        return [
            str(action.get("skill", "")).strip()
            for action in (actions or [])
            if isinstance(action, dict) and str(action.get("skill", "")).strip()
        ]

    def skill_item_weakly_matches_subtask(self, item, subtask):
        if not isinstance(item, dict) or not isinstance(subtask, dict):
            return False
        template = item.get("template") or {}
        template_skills = self.action_skill_sequence(template.get("actions") or [])
        subtask_skills = self.action_skill_sequence(subtask.get("actions") or [])
        return bool(template_skills and template_skills == subtask_skills)

    def select_skill_item_for_subtask(self, subtask):
        for index in range(self.skill_select.count()):
            item = self.skill_select.itemData(index)
            if self.skill_item_matches_subtask(item, subtask):
                self.skill_select.setCurrentIndex(index)
                return True
        weak_matches = [
            index
            for index in range(self.skill_select.count())
            if self.skill_item_weakly_matches_subtask(self.skill_select.itemData(index), subtask)
        ]
        if len(weak_matches) == 1:
            self.skill_select.setCurrentIndex(weak_matches[0])
            return True
        self.skill_select.setCurrentIndex(-1)
        return False

    def allowed_phase_actions_for_subtask(self, subtask):
        allowed = []
        for action in (subtask or {}).get("actions") or []:
            if not isinstance(action, dict):
                continue
            skill = SKILL_TEMPLATES.get(action.get("skill")) or {}
            for phase_action in skill.get("allowed_phase_actions") or []:
                if phase_action not in allowed:
                    allowed.append(phase_action)
        return allowed

    def optional_phase_actions_for_subtask(self, subtask):
        optional = []
        allowed = set(self.allowed_phase_actions_for_subtask(subtask))
        for action in (subtask or {}).get("actions") or []:
            if not isinstance(action, dict):
                continue
            skill = SKILL_TEMPLATES.get(action.get("skill")) or {}
            for phase_action in skill.get("optional_phase_actions") or []:
                if phase_action in allowed and phase_action not in optional:
                    optional.append(phase_action)
        return optional

    def add_subtask_from_inputs(self):
        subtask = self.build_subtask_from_inputs()
        if subtask is None:
            self.message_label.setText(bilingual_label("请先新增片段技能", "add a segment skill first"))
            return
        self.add_or_update_subtask(subtask)
        self.subtask_added.emit(subtask)

    def update_subtask_from_inputs(self):
        key = self.current_key()
        if key is None:
            self.message_label.setText(bilingual_label("请先选择subtask", "select a subtask first"))
            return
        subtask = self.build_subtask_from_inputs()
        if subtask is None:
            self.message_label.setText(bilingual_label("请先新增片段技能", "add a segment skill first"))
            return
        new_key = (int(subtask["start_frame"]), int(subtask["end_frame"]))
        existing = self.segments.get(key) or {}
        if new_key != key:
            self.segments.pop(key, None)
        if isinstance(existing, dict) and existing.get("phases"):
            subtask["phases"] = list(existing.get("phases") or [])
        self.segments[new_key] = subtask
        self.refresh(selected_key=new_key)
        self.subtask_updated.emit(subtask)

    def update_current_subtask(self, subtask):
        key = self.current_key()
        if key is None:
            return
        new_key = (int(subtask["start_frame"]), int(subtask["end_frame"]))
        if new_key != key:
            self.segments.pop(key, None)
        self.segments[new_key] = subtask
        self.refresh(selected_key=new_key)

    def delete_selected(self):
        key = self.current_key()
        if key is None:
            self.message_label.setText(bilingual_label("请先选择subtask", "select a subtask first"))
            return
        self.segments.pop(key, None)
        self.refresh()
        self.subtask_deleted.emit({"start_frame": int(key[0]), "end_frame": int(key[1])})

    def open_phase_dialog(self):
        key = self.current_key()
        if key is None:
            self.message_label.setText(bilingual_label("请先选择subtask", "select a subtask first"))
            return
        subtask = self.segments.get(key)
        if not isinstance(subtask, dict):
            return
        dialog = PhaseDialog(
            frame_count=self.end_frame_input.maximum(),
            current_frame=self.current_frame,
            object_options=self.scene_object_options,
            phases=subtask.get("phases") or [],
            allowed_actions=self.allowed_phase_actions_for_subtask(subtask),
            optional_actions=self.optional_phase_actions_for_subtask(subtask),
            action_targets=self.action_targets_for_subtask(subtask),
            subtask_start_frame=int(subtask.get("start_frame", key[0])),
            subtask_end_frame=int(subtask.get("end_frame", key[1])),
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        subtask["phases"] = list(dialog.phases)
        self.subtask_updated.emit(subtask)

    def add_phase(self, phase):
        key = self.current_key()
        if key is None:
            self.message_label.setText(bilingual_label("请先选择subtask", "select a subtask first"))
            return
        subtask = self.segments.get(key)
        if not isinstance(subtask, dict):
            return
        phases = list(subtask.get("phases") or [])
        phases.append(phase)
        phases.sort(key=lambda item: (int(item["start_frame"]), int(item["end_frame"])))
        subtask["phases"] = phases
        self.subtask_updated.emit(subtask)

    def action_targets_for_subtask(self, subtask):
        actions = (subtask or {}).get("actions") or []
        targets = [("primary", "主动作(primary)")]
        if len(actions) > 1:
            targets.append(("auxiliary", "辅助动作(auxiliary)"))
        return targets

    def refresh(self, selected_key=None):
        self.list_widget.clear()
        for index, (key, subtask) in enumerate(sorted(self.segments.items()), start=1):
            text = ""
            if isinstance(subtask, dict):
                text = subtask.get("text", "")
            item = QListWidgetItem(f"{index}. {key[0]}:{key[1]}  {text}")
            item.setData(Qt.UserRole, key)
            self.list_widget.addItem(item)
            if key == selected_key:
                self.list_widget.setCurrentItem(item)
        self.message_label.setText("")

    def emit_selected_segment(self, current, previous):
        if current is not None:
            key = current.data(Qt.UserRole)
            self.start_frame_input.setValue(int(key[0]))
            self.end_frame_input.setValue(int(key[1]))
            subtask = self.segments.get(key)
            state = subtask.get("state", "normal") if isinstance(subtask, dict) else "normal"
            state_index = self.state_select.findData(state)
            if state_index >= 0:
                self.state_select.setCurrentIndex(state_index)
            self.select_skill_item_for_subtask(subtask)
            self.segment_selected.emit(key)
