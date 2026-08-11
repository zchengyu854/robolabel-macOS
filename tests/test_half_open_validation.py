from __future__ import annotations

from copy import deepcopy

from common.skill_schema import (
    build_action_from_slot_values,
    build_scene_from_values,
    load_scene_templates,
    load_skill_templates,
    render_subtask_text,
    validate_annotation,
)
from lite_annotator.annotation_model import create_empty_annotation, validate_lite_annotation


def make_action():
    _, skill_templates = load_skill_templates()
    return build_action_from_slot_values(
        "custom",
        {"subject": "right_effector", "description": "move object"},
        skill_templates,
    )


def make_scene():
    scene_template = load_scene_templates()
    return build_scene_from_values(
        {
            "task_type": "object_rearrangement",
            "space": "table",
            "anchor": "table",
        },
        [
            {
                "name": "object",
                "role": "main",
                "states": ["visible"],
                "affordance": ["graspable"],
                "support_or_region": "table",
            }
        ],
        scene_template,
    )


def make_subtask(start_frame, end_frame, phases=None):
    action = make_action()
    return {
        "start_frame": start_frame,
        "end_frame": end_frame,
        "state": "normal",
        "skill_id": "test_skill",
        "coordination_mode": "single_hand",
        "actions": [action],
        "text": render_subtask_text([action]),
        "phases": phases or [],
    }


def make_annotation(subtasks, frame_count=20):
    annotation = create_empty_annotation("/tmp/episode_000000.mp4", frame_count)
    annotation["video_text"] = "task description"
    annotation["scene"] = make_scene()
    annotation["subtasks"] = subtasks
    return annotation


def test_lite_validation_accepts_contiguous_half_open_subtasks_and_phases():
    annotation = make_annotation(
        [
            make_subtask(
                0,
                10,
                phases=[
                    {
                        "start_frame": 0,
                        "end_frame": 4,
                        "action": "approach",
                        "object": "object",
                        "target_action": "primary",
                    },
                    {
                        "start_frame": 4,
                        "end_frame": 10,
                        "action": "grasp",
                        "object": "object",
                        "target_action": "primary",
                    },
                ],
            ),
            make_subtask(10, 20),
        ],
        frame_count=20,
    )

    assert validate_lite_annotation(annotation, frame_count=20) == []
    assert validate_annotation(annotation) is None


def test_schema_validation_accepts_optional_annotation_meta():
    annotation = make_annotation([make_subtask(0, 20)], frame_count=20)
    annotation["annotation_meta"] = {"source": "automatic"}

    assert validate_lite_annotation(annotation, frame_count=20) == []
    assert validate_annotation(annotation) is None


def test_action_slots_accept_structured_object_attributes():
    _, skill_templates = load_skill_templates()
    action = build_action_from_slot_values(
        "pick",
        {
            "subject": "right_effector",
            "manipulated_object": {
                "name": "block",
                "color": "red",
                "material": "wooden",
            },
            "source_anchor": {
                "name": "table",
                "color": "",
                "material": "wooden",
            },
            "grasp_anchor": "main body",
            "grasp_method": "clamp",
        },
        skill_templates,
    )

    assert action["slots"]["manipulated_object"] == {
        "name": "block",
        "color": "red",
        "material": "wooden",
    }
    assert "red wooden block" in action["text"]
    annotation = make_annotation([{
        "start_frame": 0,
        "end_frame": 20,
        "state": "normal",
        "coordination_mode": "single_hand",
        "actions": [action],
        "text": render_subtask_text([action]),
        "phases": [
            {
                "start_frame": 0,
                "end_frame": 20,
                "action": "grasp",
                "object": {
                    "name": "block",
                    "color": "red",
                    "material": "wooden",
                },
                "target_action": "primary",
            }
        ],
    }])

    assert validate_lite_annotation(annotation, frame_count=20) == []
    assert validate_annotation(annotation) is None


def test_schema_validation_accepts_hidden_standard_metadata_for_loaded_auto_annotations():
    annotation = make_annotation(
        [
            make_subtask(
                0,
                20,
                phases=[
                    {
                        "start_frame": 0,
                        "end_frame": 20,
                        "action": "approach",
                        "object": "object",
                        "target_action": "primary",
                        "prediction_meta": {"alignment_score": 0.8},
                    }
                ],
            )
        ],
        frame_count=20,
    )
    annotation["_standard_episode_entry"] = {"episode_prediction_meta": {"keep": True}}
    annotation["subtasks"][0]["prediction_meta"] = {"alignment_score": 0.9}
    annotation["subtasks"][0]["_standard_subtask_entry"] = {"review_flags": ["keep"]}

    assert validate_lite_annotation(annotation, frame_count=20) == []
    assert validate_annotation(annotation) is None


def test_schema_validation_accepts_standard_subtasks_without_skill_id():
    subtask = make_subtask(0, 20)
    subtask.pop("skill_id")
    annotation = make_annotation([subtask], frame_count=20)

    assert validate_lite_annotation(annotation, frame_count=20) == []
    assert validate_annotation(annotation) is None


def test_lite_validation_rejects_gap_between_half_open_subtasks():
    annotation = make_annotation([make_subtask(0, 10), make_subtask(11, 20)], frame_count=20)

    errors = validate_lite_annotation(annotation, frame_count=20)

    assert any("应为10" in error for error in errors)


def test_lite_validation_requires_final_subtask_end_equal_frame_count():
    annotation = make_annotation([make_subtask(0, 19)], frame_count=20)

    errors = validate_lite_annotation(annotation, frame_count=20)

    assert any("视频尾帧后一帧20" in error for error in errors)


def test_schema_validation_rejects_overlapping_half_open_phases():
    annotation = make_annotation(
        [
            make_subtask(
                0,
                10,
                phases=[
                    {
                        "start_frame": 0,
                        "end_frame": 5,
                        "action": "approach",
                        "object": "object",
                        "target_action": "primary",
                    },
                    {
                        "start_frame": 4,
                        "end_frame": 10,
                        "action": "grasp",
                        "object": "object",
                        "target_action": "primary",
                    },
                ],
            ),
            make_subtask(10, 20),
        ],
        frame_count=20,
    )

    error = validate_annotation(annotation)

    assert error is not None
    assert "上一 phase 结束帧开始" in error or "重叠" in error
