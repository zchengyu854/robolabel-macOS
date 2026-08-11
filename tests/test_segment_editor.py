from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QLabel

from lite_annotator.segment_editor import PhaseDialog, SegmentEditor
from lite_annotator.skill_form import SkillForm

_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication([])
    return _APP


def test_set_end_to_current_frame_uses_half_open_boundary():
    app()
    editor = SegmentEditor()
    editor.set_frame_count(406)
    editor.set_current_frame(405)

    editor.set_end_to_current_frame()

    assert editor.end_frame_input.value() == 406


def test_set_end_to_current_frame_clamps_to_frame_count_boundary():
    app()
    editor = SegmentEditor()
    editor.set_frame_count(406)
    editor.current_frame = 406

    editor.set_end_to_current_frame()

    assert editor.end_frame_input.value() == 406


def test_set_start_to_current_frame_reads_latest_bound_frame_source():
    app()
    editor = SegmentEditor()
    editor.set_frame_count(100)
    editor.set_current_frame(41)
    editor.bind_frame_source(lambda: 42)

    editor.set_start_to_current_frame()

    assert editor.start_frame_input.value() == 42


def test_phase_dialog_shows_subtask_start_frame_hint():
    app()

    dialog = PhaseDialog(
        frame_count=100,
        current_frame=42,
        subtask_start_frame=20,
        subtask_end_frame=60,
    )

    labels = [child.text() for child in dialog.findChildren(QLabel)]
    assert any("当前subtask范围: 20:60" in text for text in labels)
    assert any("起始帧: 20" in text for text in labels)


def test_phase_dialog_marks_optional_actions():
    app()

    dialog = PhaseDialog(
        frame_count=100,
        current_frame=42,
        allowed_actions=["align", "grasp"],
        optional_actions=["align"],
    )

    labels = [
        dialog.action_select.itemText(index)
        for index in range(dialog.action_select.count())
    ]
    assert any("align" in label and "可选" in label for label in labels)
    assert any("grasp" in label and "可选" not in label for label in labels)


def test_skill_form_renders_start_and_end_boundaries():
    app()

    form = SkillForm()
    form.render_skill_info(
        {
            "meaning": "测试含义",
            "start_frame_definition": "开始规则",
            "end_frame_definition": "结束规则",
            "allowed_phase_actions": [],
        }
    )

    text = form.skill_info.toPlainText()
    assert "开始边界: 开始规则" in text
    assert "结束边界: 结束规则" in text


def test_press_position_anchor_allows_scene_object_options():
    app()

    form = SkillForm(
        scene_object_options={
            "button_box": {
                "name": "button box",
                "color": "red",
                "material": "plastic",
                "label": "red plastic button box",
            }
        }
    )
    for index in range(form.skill_select.count()):
        if form.skill_select.itemData(index) == "press":
            form.skill_select.setCurrentIndex(index)
            break

    editor = form.slot_widgets["position_anchor"]

    assert editor.findData(
        {"name": "button box", "color": "red", "material": "plastic"}
    ) >= 0
    assert editor.findData("top") >= 0


def test_selecting_subtask_matches_skill_template_without_skill_id():
    app()

    editor = SegmentEditor()
    template_a = {
        "coordination_mode": "single_hand",
        "actions": [
            {
                "subject": "right_effector",
                "skill": "pick",
                "slots": {"manipulated_object": "block"},
                "text": "right_effector pick block",
            }
        ],
        "text": "right_effector pick block",
    }
    template_b = {
        "coordination_mode": "single_hand",
        "actions": [
            {
                "subject": "right_effector",
                "skill": "place",
                "slots": {"manipulated_object": "block"},
                "text": "right_effector place block",
            }
        ],
        "text": "right_effector place block",
    }
    editor.set_skill_items([
        {"id": "skill_a", "text": template_a["text"], "template": template_a},
        {"id": "skill_b", "text": template_b["text"], "template": template_b},
    ])
    editor.set_segments([
        {
            "start_frame": 0,
            "end_frame": 10,
            "skill_id": "skill_a",
            **template_a,
        },
        {
            "start_frame": 10,
            "end_frame": 20,
            **template_b,
        },
    ])

    editor.list_widget.setCurrentRow(1)

    assert editor.skill_select.currentData()["id"] == "skill_b"


def test_selecting_subtask_falls_back_to_unique_skill_type_match():
    app()

    editor = SegmentEditor()
    editor.set_skill_items([
        {
            "id": "skill_pick",
            "text": "right_effector pick up yellow banana from white table",
            "template": {
                "actions": [
                    {
                        "skill": "pick",
                        "subject": "right_effector",
                        "slots": {"manipulated_object": "yellow banana"},
                    }
                ],
                "text": "right_effector pick up yellow banana from white table",
            },
        },
        {
            "id": "skill_place",
            "text": "right_effector place yellow banana on yellow basket",
            "template": {
                "actions": [{"skill": "place", "subject": "right_effector"}],
                "text": "right_effector place yellow banana on yellow basket",
            },
        },
    ])
    editor.set_segments([
        {
            "start_frame": 0,
            "end_frame": 10,
            "actions": [
                {
                    "skill": "pick",
                    "subject": "right_effector",
                    "slots": {"manipulated_object": "banana"},
                }
            ],
            "text": "right_effector pick up banana from left",
        }
    ])

    editor.list_widget.setCurrentRow(0)

    assert editor.skill_select.currentData()["id"] == "skill_pick"


def test_selecting_subtask_clears_skill_when_no_template_matches():
    app()

    editor = SegmentEditor()
    editor.set_skill_items([
        {
            "id": "skill_pick",
            "text": "right_effector pick up banana",
            "template": {"actions": [{"skill": "pick"}], "text": "right_effector pick up banana"},
        }
    ])
    editor.set_segments([
        {
            "start_frame": 0,
            "end_frame": 10,
            "actions": [{"skill": "pour"}],
            "text": "right_effector pour water",
        }
    ])

    editor.list_widget.setCurrentRow(0)

    assert editor.skill_select.currentIndex() == -1


def test_set_empty_segments_clears_previous_subtask_form_state():
    app()

    editor = SegmentEditor()
    editor.set_frame_count(100)
    editor.set_skill_items([
        {
            "id": "skill_pick",
            "text": "right_effector pick up banana",
            "template": {
                "actions": [{"skill": "pick"}],
                "text": "right_effector pick up banana",
            },
        }
    ])
    editor.set_segments([
        {
            "start_frame": 12,
            "end_frame": 34,
            "skill_id": "skill_pick",
            "actions": [{"skill": "pick"}],
            "text": "right_effector pick up banana",
        }
    ])
    editor.list_widget.setCurrentRow(0)

    editor.set_segments([])

    assert editor.list_widget.count() == 0
    assert editor.start_frame_input.value() == 0
    assert editor.end_frame_input.value() == 0
    assert editor.state_select.currentData() == "normal"
    assert editor.skill_select.currentIndex() == -1


def test_update_current_subtask_rekeys_segment_when_frame_span_changes():
    app()

    editor = SegmentEditor()
    editor.set_frame_count(100)
    editor.set_segments([
        {
            "start_frame": 0,
            "end_frame": 10,
            "actions": [{"skill": "pick"}],
            "text": "right_effector pick up banana",
        }
    ])
    editor.list_widget.setCurrentRow(0)

    editor.update_current_subtask({
        "start_frame": 0,
        "end_frame": 20,
        "actions": [{"skill": "pick"}],
        "text": "right_effector pick up banana",
    })

    assert (0, 10) not in editor.segments
    assert (0, 20) in editor.segments
    assert editor.list_widget.item(0).text().startswith("1. 0:20")
    assert editor.list_widget.item(0).data(Qt.UserRole) == (0, 20)
