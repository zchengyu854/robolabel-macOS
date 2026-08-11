from __future__ import annotations

import json
from pathlib import Path

from common.skill_schema import load_skill_templates


PHASE_ACTIONS_PATH = Path(__file__).resolve().parents[1] / "config" / "phase_actions.json"


def test_anchor_slots_allow_effector_positions():
    _, skills = load_skill_templates()
    for skill in skills.values():
        enum_constraints = skill.get("enum_constraints") or {}
        for slot in ("source_anchor", "destination_anchor"):
            if slot not in enum_constraints:
                continue
            values = enum_constraints[slot]
            assert "left_effector" in values
            assert "right_effector" in values


def test_phase_actions_include_latest_boundary_rules():
    phase_actions = {
        item["value"]: item
        for item in json.loads(PHASE_ACTIONS_PATH.read_text(encoding="utf-8"))
    }

    expected = {
        "approach": (
            "末端在未接触或控制目标时，持续向目标靠近。",
            "末端开始朝目标移动，且末端与目标距离持续减小的第一帧。",
            "末端开始精细对准、接触目标、闭合夹爪或执行具体操作前的第一帧。",
        ),
        "carry": (
            "夹持物体状态下，末端 / 机械臂带着物体空间移动，物体不持续依托支撑面运动。",
            "被持物结束 grasp、secure 或 lift 后，开始进行明显空间移动的第一帧。",
            "主要空间移动停止，运动转为精细 align、lower、insert、pour 或其他目标操作的第一帧。",
        ),
        "pour_motion": (
            "使液体、颗粒或粉末从源容器转移至目标容器或目标区域。",
            "被控制的容器变成比水平面略低几度，或容器开始流出液体的第一帧；",
            "被控制的容器变成比水平面略高几度，或容器停止流出液体的第一帧；",
        ),
        "idle": (
            "无任务动作",
            "无任务相关动作开始",
            "开始其他有效操作的第一帧。",
        ),
    }
    for phase_id, (meaning, start_boundary, end_boundary) in expected.items():
        phase = phase_actions[phase_id]
        assert phase["meaning"] == meaning
        assert phase["start_frame_definition"] == start_boundary
        assert phase["end_frame_definition"] == end_boundary


def test_skill_start_and_end_boundaries_follow_latest_annotation_rules():
    _, skills = load_skill_templates()

    expected_boundaries = {
        "hold": (
            "末端夹取物品停止移动的第一帧；（根据主观判断当前的动作类型是否发生变化）",
            "末端夹取物品开始移动的第一帧；（根据主观判断当前的动作类型是否发生变化）",
        ),
        "transfer": (
            "紧接末端pick之后。",
            "末端夹取物品停止移动的第一帧；",
        ),
        "twist": (
            "紧接末端pick之后。",
            "末端完全张开的第一帧；",
        ),
        "pick": (
            "末端开始朝目标物体连续移动；",
            "末端完全闭合的第一帧；",
        ),
        "place": (
            "末端开始朝目标位置连续移动；",
            "末端完全放开的第一帧；",
        ),
        "press": (
            "末端开始朝目标位置连续移动；",
            "末端离开接触物体的第一帧；",
        ),
        "push": (
            "末端开始朝目标位置连续移动；",
            "末端离开接触物体的第一帧；",
        ),
        "pull": (
            "紧接pick之后，末端开始朝目标位置连续移动；",
            "末端离开接触物体的第一帧；",
        ),
        "cut": (
            "紧接pick之后，末端开始朝目标位置连续移动；",
            "末端离开接触物体的第一帧；",
        ),
        "stir": (
            "紧接pick之后，末端开始朝目标位置连续移动；",
            "末端的工具离开接触物体的第一帧；",
        ),
        "pour": (
            "紧接pick之后，末端开始朝目标位置连续移动；",
            "被控制的容器变成比水平面略高几度，容器停止流出物体的第一帧；",
        ),
        "fold": (
            "末端开始朝目标位置连续移动；",
            "末端完全张开的第一帧；",
        ),
        "slide": (
            "末端开始朝目标位置连续移动；",
            "末端完全张开的第一帧；",
        ),
        "insert": (
            "紧接pick之后，末端开始朝目标位置连续移动；",
            "末端完全张开的第一帧；",
        ),
        "throw": (
            "紧接pick之后，末端开始朝目标位置连续移动；",
            "末端完全张开的第一帧；",
        ),
        "open": (
            "末端开始朝目标位置连续移动；",
            "末端离开接触物体的第一帧；",
        ),
        "close": (
            "末端开始朝目标位置连续移动；",
            "末端离开接触物体的第一帧；",
        ),
        "zip": (
            "紧接pick之后，末端开始朝目标位置连续移动；",
            "末端完全张开的第一帧；",
        ),
        "unzip": (
            "紧接pick之后，末端开始朝目标位置连续移动；",
            "末端完全张开的第一帧；",
        ),
        "hand_over": (
            "紧接pick之后，末端开始朝目标位置连续移动；",
            "末端完全放开的第一帧；",
        ),
        "navigate": (
            "底盘开始移动；",
            "底盘结束移动的第一帧；",
        ),
        "return_to_initial_pose": (
            "紧接上一个skill结束，末端开始返回初始位置；",
            "末端回到初始位置，停止移动的第一帧；",
        ),
    }

    for skill_id, (start_boundary, end_boundary) in expected_boundaries.items():
        skill = skills[skill_id]
        assert skill["start_frame_definition"] == start_boundary
        assert skill["end_frame_definition"] == end_boundary


def test_return_to_initial_pose_skill_is_available():
    _, skills = load_skill_templates()
    skill = skills["return_to_initial_pose"]

    assert skill["display_name"] == "回到初始位姿/复位"
    assert skill["template"] == "[subject] return to initial pose"
    assert skill["ui_template"] == "[subject] 回到初始位姿"
    assert skill["required_slots"] == ["subject"]
    assert skill["enum_constraints"]["subject"] == [
        "effector",
        "left_effector",
        "right_effector",
        "both_effectors",
        "unknown",
    ]
    assert skill["allowed_phase_actions"] == ["retreat"]


def test_zip_and_unzip_skills_are_available_with_simple_slots():
    _, skills = load_skill_templates()
    expected_phase_actions = [
        "pull_motion",
        "release",
    ]

    zip_skill = skills["zip"]
    assert zip_skill["template"] == (
        "[subject] zip [interaction_target] from [source_anchor] to [destination_anchor]"
    )
    assert zip_skill["ui_template"] == (
        "[subject] 拉上/闭合 [interaction_target]，从 [source_anchor] 到 [destination_anchor]"
    )
    assert zip_skill["required_slots"] == [
        "subject",
        "interaction_target",
        "source_anchor",
        "destination_anchor",
    ]
    assert zip_skill["allowed_phase_actions"] == expected_phase_actions

    unzip_skill = skills["unzip"]
    assert unzip_skill["template"] == (
        "[subject] unzip [interaction_target] from [source_anchor] to [destination_anchor]"
    )
    assert unzip_skill["ui_template"] == (
        "[subject] 拉开/打开 [interaction_target]，从 [source_anchor] 到 [destination_anchor]"
    )
    assert unzip_skill["required_slots"] == zip_skill["required_slots"]
    assert unzip_skill["allowed_phase_actions"] == expected_phase_actions


def test_common_tool_and_state_skills_are_available_with_simple_slots():
    _, skills = load_skill_templates()
    expected = {
        "open": {
            "template": "[subject] open [interaction_target] with [physical_motion]",
            "ui_template": "[subject] 用 [physical_motion] 打开 [interaction_target]",
            "required_slots": ["subject", "interaction_target", "physical_motion"],
            "allowed_phase_actions": [
                "approach",
                "align",
                "grasp",
                "pull_motion",
                "push_motion",
                "press_motion",
                "release",
            ],
        },
        "close": {
            "template": "[subject] close [interaction_target] with [physical_motion]",
            "ui_template": "[subject] 用 [physical_motion] 关闭 [interaction_target]",
            "required_slots": ["subject", "interaction_target", "physical_motion"],
            "allowed_phase_actions": [
                "approach",
                "align",
                "grasp",
                "pull_motion",
                "push_motion",
                "press_motion",
                "release",
            ],
        },
        "scoop": {
            "template": "[subject] scoop [substance] from [source_container] with [tool]",
            "ui_template": "[subject] 用 [tool] 从 [source_container] 舀取 [substance]",
            "required_slots": ["subject", "substance", "source_container", "tool"],
            "allowed_phase_actions": [
                "carry",
                "align",
                "rotate_motion",
                "slide_motion",
                "lift",
            ],
        },
        "cut": {
            "template": "[subject] cut [interaction_target] with [tool]",
            "ui_template": "[subject] 用 [tool] 切割 [interaction_target]",
            "required_slots": ["subject", "interaction_target", "tool"],
            "allowed_phase_actions": [
                "carry",
                "align",
                "press_motion",
                "slide_motion",
                "lift",
            ],
        },
        "hold": {
            "template": "[subject] hold [interaction_target]",
            "ui_template": "[subject] 固定/保持 [interaction_target]",
            "required_slots": ["subject", "interaction_target"],
            "allowed_phase_actions": [
                "secure",
            ],
        },
        "stir": {
            "template": "[subject] stir [substance] in [destination_container] with [tool]",
            "ui_template": "[subject] 用 [tool] 搅拌 [destination_container] 中的 [substance]",
            "required_slots": ["subject", "substance", "destination_container", "tool"],
            "allowed_phase_actions": [
                "carry",
                "align",
                "insert_motion",
                "rotate_motion",
            ],
        },
    }

    for skill_id, expected_skill in expected.items():
        skill = skills[skill_id]
        assert skill["template"] == expected_skill["template"]
        assert skill["ui_template"] == expected_skill["ui_template"]
        assert skill["required_slots"] == expected_skill["required_slots"]
        assert skill["allowed_phase_actions"] == expected_skill["allowed_phase_actions"]

    for skill_id in ("open", "close"):
        skill = skills[skill_id]
        assert skill["slot_display_names"]["physical_motion"] == "物理动作方式"
        assert skill["enum_constraints"]["physical_motion"] == [
            "pull_motion",
            "push_motion",
            "press_motion",
        ]
        assert skill["enum_display_names"]["physical_motion"] == {
            "pull_motion": "拉动",
            "push_motion": "推动",
            "press_motion": "按压",
        }


def test_stir_substance_uses_pourable_substance_enum():
    _, skills = load_skill_templates()

    assert skills["stir"]["enum_constraints"]["substance"] == [
        "liquid",
        "granules",
        "powder",
        "solid_items",
        "mixed_contents",
        "unknown",
    ]


def test_hand_over_skill_is_available_with_receiver_slot():
    _, skills = load_skill_templates()
    skill = skills["hand_over"]

    assert skill["display_name"] == "递交/交接"
    assert skill["template"] == "[subject] hand over [manipulated_object] to [destination_anchor]"
    assert skill["ui_template"] == "[subject] 将 [manipulated_object] 递交给 [destination_anchor]"
    assert skill["required_slots"] == [
        "subject",
        "manipulated_object",
        "destination_anchor",
    ]
    assert skill["slot_display_names"]["destination_anchor"] == "接收方/目标位置"
    assert "left_effector" in skill["enum_constraints"]["destination_anchor"]
    assert "right_effector" in skill["enum_constraints"]["destination_anchor"]
    assert "person" in skill["enum_constraints"]["destination_anchor"]
    assert skill["enum_display_names"]["destination_anchor"]["person"] == "人/接收人"
    assert skill["allowed_phase_actions"] == [
        "align",
        "grasp",
        "release",
    ]


def test_skill_phase_actions_follow_carry_when_holding_object_or_tool_rule():
    _, skills = load_skill_templates()

    assert skills["hold"]["allowed_phase_actions"] == ["secure"]
    assert skills["transfer"]["allowed_phase_actions"] == ["carry"]
    assert skills["twist"]["allowed_phase_actions"] == ["rotate_motion"]
    assert skills["pick"]["allowed_phase_actions"] == ["approach", "align", "grasp"]
    assert skills["place"]["allowed_phase_actions"] == [
        "carry",
        "align",
        "release",
    ]
    assert skills["press"]["allowed_phase_actions"] == ["approach", "align", "press_motion"]
    assert skills["push"]["allowed_phase_actions"] == ["approach", "align", "push_motion"]
    assert skills["pull"]["allowed_phase_actions"] == [
        "approach",
        "align",
        "pull_motion",
    ]
    assert skills["pour"]["allowed_phase_actions"] == [
        "carry",
        "align",
        "tilt_motion",
        "pour_motion",
    ]
    assert skills["fold"]["allowed_phase_actions"] == [
        "approach",
        "align",
        "grasp",
        "fold_motion",
        "release",
    ]
    assert skills["slide"]["allowed_phase_actions"] == [
        "approach",
        "align",
        "grasp",
        "slide_motion",
        "release",
    ]
    assert skills["insert"]["allowed_phase_actions"] == [
        "carry",
        "align",
        "insert_motion",
        "release",
    ]
    assert skills["shake"]["allowed_phase_actions"] == [
        "secure",
        "shake_motion",
        "release",
    ]
    assert skills["strike"]["allowed_phase_actions"] == [
        "carry",
        "align",
        "strike_motion",
    ]
    assert skills["throw"]["allowed_phase_actions"] == [
        "carry",
        "align",
        "release",
    ]
    assert skills["wipe_scrub"]["allowed_phase_actions"] == [
        "carry",
        "align",
        "scrub_motion",
        "release",
    ]


def test_optional_phase_actions_are_marked_in_skill_templates():
    _, skills = load_skill_templates()

    expected_optional = {
        "pick": ["align"],
        "place": ["align"],
        "press": ["align"],
        "push": ["align"],
        "pull": ["align"],
        "open": ["align", "release"],
        "close": ["align", "release"],
        "scoop": ["align"],
        "cut": ["align", "slide_motion"],
        "stir": ["align", "insert_motion"],
        "pour": ["align"],
        "fold": ["align", "release"],
        "slide": ["align", "release"],
        "insert": ["align", "release"],
        "shake": ["release"],
        "strike": ["align"],
        "throw": ["align"],
        "hand_over": ["align"],
        "wipe_scrub": ["align", "release"],
    }

    for skill_id, optional_actions in expected_optional.items():
        skill = skills[skill_id]
        assert skill.get("optional_phase_actions") == optional_actions
        for phase_action in optional_actions:
            assert phase_action in skill["allowed_phase_actions"]
