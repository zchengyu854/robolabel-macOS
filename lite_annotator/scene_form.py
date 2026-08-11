from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from common.skill_schema import build_scene_from_values, load_scene_templates
from lite_annotator.object_attributes import (
    extract_named_options,
    object_color,
    object_display_label,
    object_material,
    object_name,
    object_ref_text,
)
from lite_annotator.ui_text import bilingual_label
from lite_annotator.vocabulary import (
    extract_object_options,
    extract_space_options,
    load_vocabulary,
    option_label,
    value_from_option_text,
)

SCENE_TEMPLATE = load_scene_templates()
VOCABULARY = load_vocabulary()
SPACE_OPTIONS = extract_space_options(VOCABULARY)
OBJECT_OPTIONS = extract_object_options(VOCABULARY)
COLOR_OPTIONS = extract_named_options(VOCABULARY, "object_colors")
MATERIAL_OPTIONS = extract_named_options(VOCABULARY, "object_materials")
AFFORDANCE_OPTIONS = {
    value: SCENE_TEMPLATE.get("enum_display_names", {})
    .get("affordance", {})
    .get(value, value)
    for value in SCENE_TEMPLATE.get("enum_constraints", {}).get("affordance", [])
}
EFFECTOR_TYPE_OPTIONS = {
    "two_finger": "二指末端",
    "three_finger": "三指末端",
    "four_finger": "四指末端",
    "five_finger": "五指末端",
}
ROBOT_EMBODIMENT_OPTIONS = {
    "dual_arm": "双臂",
    "single_arm": "单臂",
}
BASE_MOBILITY_OPTIONS = {
    "unknown": "未知",
    "fixed": "固定底座",
    "mobile": "移动底盘",
}


class ObjectEditDialog(QDialog):
    def __init__(
        self,
        object_value="",
        affordance=None,
        parent=None,
        allow_name_edit=True,
        color="",
        material="",
    ):
        super().__init__(parent)
        self.setWindowTitle(bilingual_label("物品属性", "object attributes"))
        affordance = affordance or []

        self.object_combo = QComboBox()
        self.object_combo.setEditable(True)
        self.object_combo.setInsertPolicy(QComboBox.NoInsert)
        self.object_combo.setMaxVisibleItems(24)
        for value, label in OBJECT_OPTIONS.items():
            self.object_combo.addItem(option_label(value, label), value)
        completer = QCompleter(
            [self.object_combo.itemText(i) for i in range(self.object_combo.count())],
            self.object_combo,
        )
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.object_combo.setCompleter(completer)
        self.set_combo_value(self.object_combo, object_value)
        self.object_combo.setEnabled(bool(allow_name_edit))

        self.color_combo = QComboBox()
        self.color_combo.addItem("-", "")
        for value, label in COLOR_OPTIONS.items():
            self.color_combo.addItem(option_label(value, label), value)
        self.set_combo_value(self.color_combo, color)

        self.material_combo = QComboBox()
        self.material_combo.addItem("-", "")
        for value, label in MATERIAL_OPTIONS.items():
            self.material_combo.addItem(option_label(value, label), value)
        self.set_combo_value(self.material_combo, material)

        self.affordance_list = QListWidget()
        self.affordance_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for value, label in AFFORDANCE_OPTIONS.items():
            item = QListWidgetItem(option_label(value, label))
            item.setData(Qt.UserRole, value)
            self.affordance_list.addItem(item)
            item.setSelected(value in affordance)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText(bilingual_label("确定", "ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(bilingual_label("取消", "cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow(bilingual_label("物品", "object"), self.object_combo)
        form.addRow(bilingual_label("颜色", "color"), self.color_combo)
        form.addRow(bilingual_label("材质", "material"), self.material_combo)
        form.addRow(bilingual_label("Affordance", "affordance"), self.affordance_list)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def set_combo_value(self, combo, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        elif value:
            if combo.isEditable():
                combo.setEditText(str(value))
            else:
                combo.addItem(str(value), str(value))
                combo.setCurrentIndex(combo.count() - 1)

    def object_value(self):
        text_value = value_from_option_text(self.object_combo.currentText().strip(), OBJECT_OPTIONS)
        return text_value or str(self.object_combo.currentData() or "")

    def affordance_values(self):
        return [
            self.affordance_list.item(index).data(Qt.UserRole)
            for index in range(self.affordance_list.count())
            if self.affordance_list.item(index).isSelected()
        ]

    def color_value(self):
        return str(self.color_combo.currentData() or "")

    def material_value(self):
        return str(self.material_combo.currentData() or "")

    def object_data(self):
        return {
            "name": self.object_value(),
            "color": self.color_value(),
            "material": self.material_value(),
            "affordance": self.affordance_values(),
        }


class SceneForm(QWidget):
    scene_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_type = QComboBox()
        for task_type in SCENE_TEMPLATE.get("enum_constraints", {}).get("task_type", []):
            label = (
                SCENE_TEMPLATE.get("enum_display_names", {})
                .get("task_type", {})
                .get(task_type, task_type)
            )
            self.task_type.addItem(option_label(task_type, label), task_type)

        self.space = QComboBox()
        self.space.setEditable(True)
        for value, label in SPACE_OPTIONS.items():
            self.space.addItem(option_label(value, label), value)
        self.robot_embodiment = QComboBox()
        for value, label in ROBOT_EMBODIMENT_OPTIONS.items():
            self.robot_embodiment.addItem(option_label(value, label), value)
        self.base_mobility_type = QComboBox()
        for value, label in BASE_MOBILITY_OPTIONS.items():
            self.base_mobility_type.addItem(option_label(value, label), value)
        self.single_effector_type = self.create_effector_type_combo()
        self.left_effector_type = self.create_effector_type_combo()
        self.right_effector_type = self.create_effector_type_combo()
        self.task_type.currentIndexChanged.connect(self.scene_changed.emit)
        self.space.currentIndexChanged.connect(self.scene_changed.emit)
        self.space.editTextChanged.connect(self.scene_changed.emit)
        self.robot_embodiment.currentIndexChanged.connect(self.update_robot_setup_visibility)
        self.robot_embodiment.currentIndexChanged.connect(self.scene_changed.emit)
        self.base_mobility_type.currentIndexChanged.connect(self.scene_changed.emit)
        self.single_effector_type.currentIndexChanged.connect(self.scene_changed.emit)
        self.left_effector_type.currentIndexChanged.connect(self.scene_changed.emit)
        self.right_effector_type.currentIndexChanged.connect(self.scene_changed.emit)

        self.objects = []
        self.referenced_objects = set()
        self.objects_list = QListWidget()
        self.objects_list.setMaximumHeight(170)
        self.message_label = QLabel("")
        self.add_object_button = QPushButton(bilingual_label("增加物品", "add object"))
        self.add_object_button.setFixedWidth(150)
        self.add_object_button.clicked.connect(self.open_add_object_dialog)
        self.edit_object_button = QPushButton(bilingual_label("编辑", "edit"))
        self.edit_object_button.clicked.connect(self.open_edit_object_dialog)
        self.delete_object_button = QPushButton(bilingual_label("删除", "delete"))
        self.delete_object_button.clicked.connect(self.delete_selected_object)

        form = QFormLayout()
        form.addRow(bilingual_label("任务类型", "task type"), self.task_type)
        form.addRow(bilingual_label("空间", "space"), self.space)
        form.addRow(bilingual_label("机器人形态", "robot embodiment"), self.robot_embodiment)
        form.addRow(bilingual_label("底盘移动类型", "base mobility type"), self.base_mobility_type)
        self.single_effector_label = QLabel(bilingual_label("末端类型", "effector type"))
        self.left_effector_label = QLabel(bilingual_label("左手末端类型", "left effector type"))
        self.right_effector_label = QLabel(bilingual_label("右手末端类型", "right effector type"))
        form.addRow(self.single_effector_label, self.single_effector_type)
        form.addRow(self.left_effector_label, self.left_effector_type)
        form.addRow(self.right_effector_label, self.right_effector_type)
        objects_box = QWidget()
        objects_layout = QVBoxLayout(objects_box)
        objects_layout.setContentsMargins(0, 0, 0, 0)
        objects_layout.addWidget(self.objects_list)
        object_buttons = QHBoxLayout()
        object_buttons.addWidget(self.add_object_button)
        object_buttons.addWidget(self.edit_object_button)
        object_buttons.addWidget(self.delete_object_button)
        objects_layout.addLayout(object_buttons)
        objects_layout.addWidget(self.message_label)
        form.addRow(bilingual_label("物品", "objects"), objects_box)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        self.update_robot_setup_visibility()

    def create_effector_type_combo(self):
        combo = QComboBox()
        for value, label in EFFECTOR_TYPE_OPTIONS.items():
            combo.addItem(option_label(value, label), value)
        return combo

    def update_robot_setup_visibility(self):
        is_single_arm = self.robot_embodiment.currentData() == "single_arm"
        self.single_effector_label.setVisible(is_single_arm)
        self.single_effector_type.setVisible(is_single_arm)
        self.left_effector_label.setVisible(not is_single_arm)
        self.left_effector_type.setVisible(not is_single_arm)
        self.right_effector_label.setVisible(not is_single_arm)
        self.right_effector_type.setVisible(not is_single_arm)

    def add_object_item(self, value="", affordance=None, color="", material=""):
        if isinstance(value, dict):
            color = object_color(value)
            material = object_material(value)
            value = object_name(value)
        self.objects.append({
            "name": str(value).strip(),
            "color": str(color).strip(),
            "material": str(material).strip(),
            "affordance": list(affordance or []),
        })
        self.refresh_object_list()
        self.scene_changed.emit()

    def add_object_row(self, value="", affordance=None):
        self.add_object_item(value, affordance)

    def set_referenced_objects(self, values):
        self.referenced_objects = {
            str(value).strip()
            for value in (values or set())
            if str(value).strip()
        }

    def open_add_object_dialog(self):
        dialog = ObjectEditDialog(parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.object_data()
        if data["name"]:
            self.add_object_item(
                data["name"],
                data["affordance"],
                data["color"],
                data["material"],
            )

    def open_edit_object_dialog(self):
        row = self.objects_list.currentRow()
        if row < 0 or row >= len(self.objects):
            return
        current = self.objects[row]
        dialog = ObjectEditDialog(
            current.get("name", ""),
            current.get("affordance") or [],
            self,
            allow_name_edit=False,
            color=current.get("color", ""),
            material=current.get("material", ""),
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.object_data()
        name = str(current.get("name", "")).strip()
        if name:
            self.objects[row] = {
                "name": name,
                "color": data["color"],
                "material": data["material"],
                "affordance": data["affordance"],
            }
            self.refresh_object_list(selected_row=row)
            self.scene_changed.emit()

    def delete_selected_object(self):
        row = self.objects_list.currentRow()
        if row < 0 or row >= len(self.objects):
            return
        name = str(self.objects[row].get("name", "")).strip()
        ref_text = object_ref_text(self.objects[row])
        if name in self.referenced_objects or ref_text in self.referenced_objects:
            self.message_label.setText("该物品已被后续标注使用，不能删除。")
            return
        self.objects.pop(row)
        self.refresh_object_list()
        self.message_label.setText("")
        self.scene_changed.emit()

    def refresh_object_list(self, selected_row=None):
        self.objects_list.clear()
        for obj in self.objects:
            name = obj.get("name", "")
            affordance = obj.get("affordance") or []
            name_label = object_display_label(
                obj,
                OBJECT_OPTIONS,
                COLOR_OPTIONS,
                MATERIAL_OPTIONS,
            ) if name else ""
            summary = ", ".join(
                option_label(value, AFFORDANCE_OPTIONS.get(value, value))
                for value in affordance
            ) if affordance else "-"
            item = QListWidgetItem(f"{name_label}  {summary}")
            self.objects_list.addItem(item)
        if selected_row is not None and self.objects_list.count():
            self.objects_list.setCurrentRow(min(selected_row, self.objects_list.count() - 1))

    def selected_space_value(self):
        data = self.space.currentData()
        if data:
            return str(data)
        return self.space.currentText().strip()

    def selected_object_values(self):
        values = []
        for obj in self.objects:
            value = str(obj.get("name", "")).strip()
            if value and value not in values:
                values.append(value)
        return values

    def selected_object_options(self):
        return {
            index: {
                "name": str(obj.get("name", "")).strip(),
                "color": str(obj.get("color", "")).strip(),
                "material": str(obj.get("material", "")).strip(),
                "label": object_display_label(
                    obj,
                    OBJECT_OPTIONS,
                    COLOR_OPTIONS,
                    MATERIAL_OPTIONS,
                ),
            }
            for index, obj in enumerate(self.objects)
            if str(obj.get("name", "")).strip()
        }

    def build_robot_setup(self):
        embodiment = str(self.robot_embodiment.currentData() or "dual_arm")
        if embodiment == "single_arm":
            return {
                "embodiment": "single_arm",
                "base_mobility_type": str(self.base_mobility_type.currentData() or "unknown"),
                "single_effector_type": str(self.single_effector_type.currentData() or "two_finger"),
            }
        return {
            "embodiment": "dual_arm",
            "base_mobility_type": str(self.base_mobility_type.currentData() or "unknown"),
            "left_effector_type": str(self.left_effector_type.currentData() or "two_finger"),
            "right_effector_type": str(self.right_effector_type.currentData() or "two_finger"),
        }

    def load_robot_setup(self, robot_setup):
        robot_setup = robot_setup if isinstance(robot_setup, dict) else {}
        embodiment = robot_setup.get("embodiment")
        if not embodiment:
            embodiment = "single_arm" if "single_effector_type" in robot_setup else "dual_arm"
        self.set_combo_value(self.robot_embodiment, embodiment)
        self.set_combo_value(
            self.base_mobility_type,
            robot_setup.get("base_mobility_type", "unknown"),
        )
        self.set_combo_value(
            self.single_effector_type,
            robot_setup.get("single_effector_type", "two_finger"),
        )
        self.set_combo_value(
            self.left_effector_type,
            robot_setup.get("left_effector_type", "two_finger"),
        )
        self.set_combo_value(
            self.right_effector_type,
            robot_setup.get("right_effector_type", "two_finger"),
        )
        self.update_robot_setup_visibility()

    def build_scene(self):
        space = self.selected_space_value()
        objects = []
        seen = set()
        for obj in self.objects:
            name = str(obj.get("name", "")).strip()
            object_key = (
                name,
                str(obj.get("color", "")).strip(),
                str(obj.get("material", "")).strip(),
            )
            if not name or object_key in seen:
                continue
            seen.add(object_key)
            objects.append(
                {
                    "name": name,
                    "color": str(obj.get("color", "")).strip(),
                    "material": str(obj.get("material", "")).strip(),
                    "role": "main",
                    "states": ["visible"],
                    "affordance": list(obj.get("affordance") or []),
                    "support_or_region": space,
                }
            )
        return build_scene_from_values(
            {
                "task_type": self.task_type.currentData(),
                "space": space,
                "anchor": space,
            },
            objects,
            SCENE_TEMPLATE,
        )

    def load_scene(self, scene):
        if not isinstance(scene, dict):
            self.clear()
            return

        task_type = scene.get("task_type", "")
        for index in range(self.task_type.count()):
            if self.task_type.itemData(index) == task_type:
                self.task_type.setCurrentIndex(index)
                break

        location = scene.get("scene_location") or {}
        self.set_combo_value(self.space, location.get("space", ""))
        objects = scene.get("objects") or []
        self.clear_objects()
        for item in objects:
            self.add_object_item(
                item.get("name", ""),
                item.get("affordance") or [],
                item.get("color", ""),
                item.get("material", ""),
            )

    def clear(self):
        self.space.setCurrentIndex(0 if self.space.count() else -1)
        self.load_robot_setup({})
        self.clear_objects()

    def clear_objects(self):
        self.objects = []
        self.refresh_object_list()
        self.scene_changed.emit()

    def clear_object_rows(self):
        self.clear_objects()

    def set_combo_value(self, combo, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            if combo.isEditable():
                combo.setEditText(str(value))
            elif value:
                combo.addItem(str(value), str(value))
                combo.setCurrentIndex(combo.count() - 1)
