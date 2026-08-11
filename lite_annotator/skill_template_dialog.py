from __future__ import annotations

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QTextEdit,
    QVBoxLayout,
)

from common.skill_schema import (
    build_action_from_slot_values,
    load_coordination_modes,
    robot_embodiment,
    render_subtask_text,
)
from lite_annotator.skill_form import SKILL_TEMPLATES, SkillForm
from lite_annotator.ui_text import bilingual_label


class SkillTemplateDialog(QDialog):
    def __init__(self, parent=None, scene_object_options=None, robot_setup=None):
        super().__init__(parent)
        self.setWindowTitle(bilingual_label("片段技能填写", "segment skill entry"))
        self.robot_setup = dict(robot_setup or {})
        self.is_single_arm = robot_embodiment(self.robot_setup) == "single_arm"
        self.skill_form = SkillForm(
            self,
            scene_object_options=scene_object_options,
            robot_setup=self.robot_setup,
        )
        self.auxiliary_skill_form = SkillForm(
            self,
            scene_object_options=scene_object_options,
            robot_setup=self.robot_setup,
        )
        self.auxiliary_skill_form.setVisible(False)
        self.custom_skill_checkbox = QCheckBox(
            bilingual_label("自定义片段技能", "custom segment skill"),
            self,
        )
        self.custom_skill_text = QTextEdit(self)
        self.custom_skill_text.setPlaceholderText(
            bilingual_label("填写片段技能语义描述", "segment skill description")
        )
        self.custom_skill_text.setMaximumHeight(90)
        self.custom_skill_text.setVisible(False)
        self.custom_skill_checkbox.toggled.connect(self.on_custom_toggled)

        self.coordination_modes = load_coordination_modes()
        self.coordination_mode_select = QComboBox(self)
        for mode_id, mode in self.coordination_modes.items():
            if self.is_single_arm and mode_id != "single_hand":
                continue
            self.coordination_mode_select.addItem(
                bilingual_label(mode.get("display_name", mode_id), mode_id),
                mode_id,
            )
        self.set_coordination_mode("single_hand")

        self.auxiliary_action_checkbox = QCheckBox(
            bilingual_label("增加辅助动作", "add auxiliary action"),
            self,
        )
        self.auxiliary_action_checkbox.toggled.connect(self.on_auxiliary_toggled)

        coordination_group = QGroupBox(bilingual_label("协调方式", "coordination mode"), self)
        coordination_layout = QFormLayout(coordination_group)
        coordination_layout.addRow(
            bilingual_label("模式", "mode"),
            self.coordination_mode_select,
        )

        primary_group = QGroupBox(bilingual_label("主动作", "primary action"), self)
        primary_layout = QVBoxLayout(primary_group)
        primary_layout.addWidget(self.skill_form)

        auxiliary_group = QGroupBox(bilingual_label("辅助动作", "auxiliary action"), self)
        auxiliary_layout = QVBoxLayout(auxiliary_group)
        auxiliary_layout.addWidget(self.auxiliary_action_checkbox)
        auxiliary_layout.addWidget(self.auxiliary_skill_form)
        auxiliary_group.setVisible(not self.is_single_arm)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText(bilingual_label("确定", "ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(bilingual_label("取消", "cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.custom_skill_checkbox)
        layout.addWidget(self.custom_skill_text)
        layout.addWidget(coordination_group)
        layout.addWidget(primary_group)
        layout.addWidget(auxiliary_group)
        layout.addWidget(buttons)
        self.structured_groups = [coordination_group, primary_group]
        if not self.is_single_arm:
            self.structured_groups.append(auxiliary_group)

    def set_coordination_mode(self, mode_id):
        for index in range(self.coordination_mode_select.count()):
            if self.coordination_mode_select.itemData(index) == mode_id:
                self.coordination_mode_select.setCurrentIndex(index)
                return

    def on_auxiliary_toggled(self, enabled):
        if self.is_single_arm:
            self.auxiliary_action_checkbox.setChecked(False)
            self.auxiliary_skill_form.setVisible(False)
            self.set_coordination_mode("single_hand")
            return
        self.auxiliary_skill_form.setVisible(enabled)
        if enabled and self.coordination_mode_select.currentData() == "single_hand":
            self.set_coordination_mode("primary_with_support")
        elif not enabled:
            self.set_coordination_mode("single_hand")

    def on_custom_toggled(self, enabled):
        self.custom_skill_text.setVisible(enabled)
        for group in self.structured_groups:
            group.setVisible(not enabled)

    def build_action_from_form(self, skill_form, allow_empty=False):
        values = {
            key: skill_form.widget_value(widget)
            for key, widget in skill_form.slot_widgets.items()
        }
        return build_action_from_slot_values(
            skill_form.current_skill_id(),
            values,
            SKILL_TEMPLATES,
            allow_empty=allow_empty,
        )

    def build_template(self, allow_empty=False):
        if self.custom_skill_checkbox.isChecked():
            description = self.custom_skill_text.toPlainText().strip()
            if not description and not allow_empty:
                raise ValueError("自定义片段技能描述不能为空")
            action = {
                "subject": "unknown",
                "skill": "custom",
                "slots": {"description": description},
                "text": description,
            }
            return {
                "coordination_mode": "single_hand",
                "actions": [action],
                "text": description,
            }
        actions = [self.build_action_from_form(self.skill_form, allow_empty=allow_empty)]
        if self.auxiliary_action_checkbox.isChecked():
            actions.append(
                self.build_action_from_form(
                    self.auxiliary_skill_form,
                    allow_empty=allow_empty,
                )
            )
        return {
            "coordination_mode": self.coordination_mode_select.currentData() or "single_hand",
            "actions": actions,
            "text": render_subtask_text(actions),
        }
