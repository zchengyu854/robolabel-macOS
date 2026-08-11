from __future__ import annotations

import json
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QCompleter,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from common.skill_schema import (
    allowed_subjects_for_robot_setup,
    build_action_from_slot_values,
    load_skill_templates,
    render_subtask_text,
)
from lite_annotator.object_attributes import object_ref_matches
from lite_annotator.paths import resource_path
from lite_annotator.ui_text import bilingual_label

TEMPLATE_SET_VERSION, SKILL_TEMPLATES = load_skill_templates()
DEFAULT_OBJECT_SLOT_PATH = resource_path("config/skill_object_slots.json")


def load_object_slot_keys(path=DEFAULT_OBJECT_SLOT_PATH):
    path = Path(path)
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(item) for item in data.get("object_slots", [])}


OBJECT_SLOT_KEYS = load_object_slot_keys()
SCENE_OBJECT_ENUM_SLOT_KEYS = {"source_anchor", "destination_anchor", "position_anchor"}


class SkillForm(QWidget):
    def __init__(self, parent=None, scene_object_options=None, robot_setup=None):
        super().__init__(parent)
        self.slot_widgets = {}
        self.scene_object_options = scene_object_options or {}
        self.robot_setup = dict(robot_setup or {})
        self.skill_select = QComboBox()
        for skill_id, skill in SKILL_TEMPLATES.items():
            if skill_id == "custom":
                continue
            self.skill_select.addItem(
                f"{skill.get('display_name', skill_id)} ({skill_id})",
                skill_id,
            )
        self.skill_select.currentIndexChanged.connect(self.render_slots)

        self.skill_info = QTextEdit()
        self.skill_info.setReadOnly(True)
        self.skill_info.setMaximumHeight(150)
        self.form_layout = QFormLayout()
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(90)

        layout = QVBoxLayout(self)
        layout.addWidget(self.skill_select)
        layout.addWidget(self.skill_info)
        layout.addLayout(self.form_layout)
        layout.addWidget(self.preview)
        self.render_slots()

    def set_robot_setup(self, robot_setup):
        self.robot_setup = dict(robot_setup or {})
        self.render_slots()

    def current_skill_id(self):
        return self.skill_select.currentData()

    def render_slots(self):
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.slot_widgets = {}
        skill = SKILL_TEMPLATES[self.current_skill_id()]
        self.render_skill_info(skill)
        for slot in skill["required_slots"]:
            editor = self.create_slot_editor(skill, slot)
            self.slot_widgets[slot] = editor
            label = bilingual_label(skill.get("slot_display_names", {}).get(slot, slot), slot)
            self.form_layout.addRow(label, editor)
        self.update_preview()

    def render_skill_info(self, skill):
        lines = []
        if skill.get("meaning"):
            lines.append(f"含义: {skill['meaning']}")
        if skill.get("example"):
            lines.append(f"例子: {skill['example']}")
        if skill.get("annotation_note"):
            lines.append(f"补充: {skill['annotation_note']}")
        if skill.get("start_frame_definition"):
            lines.append(f"开始边界: {skill['start_frame_definition']}")
        if skill.get("end_frame_definition"):
            lines.append(f"结束边界: {skill['end_frame_definition']}")
        allowed_phase_actions = skill.get("allowed_phase_actions") or []
        if allowed_phase_actions:
            optional_phase_actions = set(skill.get("optional_phase_actions") or [])
            phase_labels = [
                f"{phase_action}(可选)"
                if phase_action in optional_phase_actions
                else phase_action
                for phase_action in allowed_phase_actions
            ]
            lines.append(f"允许phase action: {', '.join(phase_labels)}")
        self.skill_info.setText("\n".join(lines))

    def create_slot_editor(self, skill, slot):
        if slot in OBJECT_SLOT_KEYS and self.scene_object_options:
            editor = QComboBox()
            editor.setEditable(True)
            editor.setInsertPolicy(QComboBox.NoInsert)
            self.add_scene_object_options(editor)
            if editor.isEditable():
                self.attach_combo_completer(editor)
            editor.currentIndexChanged.connect(self.update_preview)
            editor.editTextChanged.connect(self.update_preview)
            return editor

        allowed_values = skill.get("enum_constraints", {}).get(slot)
        if allowed_values:
            editor = QComboBox()
            editor.setEditable(slot != "subject")
            editor.setInsertPolicy(QComboBox.NoInsert)
            display_names = skill.get("enum_display_names", {}).get(slot, {})
            if slot == "subject":
                allowed_subjects = allowed_subjects_for_robot_setup(self.robot_setup)
                allowed_values = [
                    value for value in allowed_values
                    if value in allowed_subjects
                ]
            if slot in SCENE_OBJECT_ENUM_SLOT_KEYS and self.scene_object_options:
                self.add_scene_object_options(editor)
            for value in allowed_values:
                if editor.findData(value) >= 0:
                    continue
                editor.addItem(
                    bilingual_label(display_names.get(value, value), value),
                    value,
                )
            if editor.isEditable():
                self.attach_combo_completer(editor)
            editor.currentIndexChanged.connect(self.update_preview)
            editor.editTextChanged.connect(self.update_preview)
            return editor

        editor = QLineEdit()
        editor.textChanged.connect(self.update_preview)
        return editor

    def add_scene_object_options(self, editor):
        for _, item in self.scene_object_options.items():
            if not isinstance(item, dict):
                continue
            value = {
                "name": str(item.get("name", "")).strip(),
                "color": str(item.get("color", "")).strip(),
                "material": str(item.get("material", "")).strip(),
            }
            if not value["name"]:
                continue
            if editor.findData(value) < 0:
                editor.addItem(str(item.get("label", value["name"])), value)

    def attach_combo_completer(self, combo):
        completer = QCompleter([combo.itemText(index) for index in range(combo.count())], combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        combo.setCompleter(completer)

    def widget_value(self, widget):
        if isinstance(widget, QComboBox):
            text = widget.currentText().strip()
            for index in range(widget.count()):
                item_data = widget.itemData(index)
                item_text = widget.itemText(index).strip()
                if text == item_text or object_ref_matches(item_data, text):
                    return item_data
            return text
        return widget.text().strip()

    def set_widget_value(self, widget, value):
        if isinstance(widget, QComboBox):
            for index in range(widget.count()):
                item_data = widget.itemData(index)
                if item_data == value or object_ref_matches(item_data, value):
                    widget.setCurrentIndex(index)
                    return
            widget.setEditText(str(value))
            return
        widget.setText(str(value))

    def clear_values(self):
        for widget in self.slot_widgets.values():
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            else:
                widget.clear()
        self.update_preview()

    def load_subtask(self, subtask):
        self.clear_values()
        actions = (subtask or {}).get("actions") or []
        if not actions:
            return

        action = actions[0]
        skill_id = action.get("skill")
        for index in range(self.skill_select.count()):
            if self.skill_select.itemData(index) == skill_id:
                self.skill_select.setCurrentIndex(index)
                break

        slots = action.get("slots") or {}
        subject = action.get("subject", "")
        if "subject" in self.slot_widgets:
            self.set_widget_value(self.slot_widgets["subject"], subject)
        for key, value in slots.items():
            if key in self.slot_widgets:
                self.set_widget_value(self.slot_widgets[key], value)
        self.update_preview()

    def build_subtask(self, start_frame, end_frame):
        values = {
            key: self.widget_value(widget)
            for key, widget in self.slot_widgets.items()
        }
        action = build_action_from_slot_values(
            self.current_skill_id(),
            values,
            SKILL_TEMPLATES,
        )
        actions = [action]
        return {
            "start_frame": int(start_frame),
            "end_frame": int(end_frame),
            "coordination_mode": "single_hand",
            "actions": actions,
            "text": render_subtask_text(actions),
        }

    def update_preview(self):
        try:
            subtask = self.build_subtask(0, 0)
            self.preview.setText(subtask["text"])
        except Exception as exc:
            self.preview.setText(str(exc))
