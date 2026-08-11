from __future__ import annotations

import json
from pathlib import Path

from common.skill_schema import render_subtask_text
from lite_annotator.dataset_loader import DatasetType, EpisodeItem
from lite_annotator.standard_export import (
    annotation_from_standard_episode,
    episode_annotation_source_text,
    find_standard_episode,
    mark_annotation_human_reviewed,
    to_standard_task_annotation,
)


def make_annotation(video_path: str, frames: int = 31) -> dict:
    return {
        "episode": {
            "episode_id": "episode_000000",
            "dataset_name": "Task_Name_959",
            "video_path": video_path,
            "primary_video_path": video_path,
            "views": {
                "cam_top": video_path,
                "cam_left": "/data/task/cam_left/episode_000000.mp4",
            },
            "frames": frames,
        },
        "video_text": "put banana into basket",
        "robot_setup": {
            "embodiment": "dual_arm",
            "base_mobility_type": "mobile",
            "left_effector_type": "two_finger",
            "right_effector_type": "five_finger",
        },
        "scene": {
            "task_type": "manipulation",
            "scene_location": {"space": "kitchen"},
            "objects": [
                {"name": "banana", "affordance": ["graspable"]},
                {"name": "basket", "affordance": ["receivable"]},
            ],
        },
        "subtasks": [
            {
                "start_frame": 0,
                "end_frame": 30,
                "state": "normal",
                "coordination_mode": "single_hand",
                "actions": [
                    {
                        "subject": "right_effector",
                        "skill": "pick",
                        "text": "right_effector pick up banana",
                        "slots": {
                            "manipulated_object": "banana",
                            "source_anchor": "basket",
                        },
                    }
                ],
                "phases": [
                    {
                        "target_action": "primary",
                        "start_frame": 0,
                        "end_frame": 30,
                        "action": "grasp",
                        "object": "banana",
                    }
                ],
            }
        ],
    }


def test_task_export_uses_task_level_schema_and_numeric_ids():
    bundle = {
        "task": {
            "video_text": "put banana into basket",
            "scene": make_annotation("/data/task/cam_top/episode_000000.mp4")["scene"],
            "robot_setup": make_annotation("/data/task/cam_top/episode_000000.mp4")["robot_setup"],
        },
        "annotations": {
            "episode_000000": make_annotation("/data/task/cam_top/episode_000000.mp4"),
        },
    }

    standard = to_standard_task_annotation(
        bundle,
        dataset_type=DatasetType.COROBOT,
        dataset_root="/data/task",
        primary_video_paths={"episode_000000": "/data/task/cam_top/episode_000000.mp4"},
    )

    assert standard["version"] == "annotation_schema_v1"
    assert standard["annotation_spec_version"] == "skill_spec_v1"
    assert standard["data_type"] == "corobot"
    assert standard["data_path"] == "/data/task"
    assert standard["cameras"] == [
        {"id": 0, "name": "cam_top", "role": "primary"},
        {"id": 1, "name": "cam_left", "role": "secondary"},
    ]
    assert standard["robot_setup"]["manipulators"] == [
        {"id": 0, "mount_position": "left", "end_effector_type": "two_finger"},
        {"id": 1, "mount_position": "right", "end_effector_type": "five_finger"},
    ]
    assert standard["scene"]["objects"] == [
        {"id": 0, "name": "banana", "affordance": ["graspable"]},
        {"id": 1, "name": "basket", "affordance": ["receivable"]},
    ]
    assert standard["skills"] == [
        {
            "id": 0,
            "skill_type": "pick",
            "name": "pick",
            "text": "right_effector pick up banana",
            "actions": [
                {
                    "role": "primary",
                    "subject": "right_effector",
                    "skill": "pick",
                    "text": "right_effector pick up banana",
                    "slots": {
                        "manipulated_object": "banana",
                        "source_anchor": "basket",
                    },
                }
            ],
            "source": "human",
            "created_by": "tool",
            "is_custom": False,
        }
    ]
    episode = standard["episode_annotation"][0]
    assert episode["id"] == 0
    assert episode["episode_video_path"] == "/data/task/cam_top/episode_000000.mp4"
    assert episode["subtasks"][0]["id"] == 0
    assert episode["subtasks"][0]["skill_id"] == 0
    assert episode["subtasks"][0]["skill_match"] == {
        "method": "exact_actions",
        "confidence": 1.0,
        "review_required": False,
    }
    assert episode["subtasks"][0]["primary_action"]["phases"][0]["id"] == 0


def test_task_export_preserves_structured_object_attributes():
    annotation = make_annotation("/data/task/cam_top/episode_000000.mp4")
    annotation["scene"]["objects"] = [
        {
            "name": "block",
            "color": "red",
            "material": "wooden",
            "affordance": ["graspable"],
        }
    ]
    object_ref = {"name": "block", "color": "red", "material": "wooden"}
    annotation["subtasks"][0]["actions"][0]["slots"]["manipulated_object"] = object_ref
    annotation["subtasks"][0]["phases"][0]["object"] = object_ref
    bundle = {
        "task": {
            "video_text": annotation["video_text"],
            "scene": annotation["scene"],
            "robot_setup": annotation["robot_setup"],
        },
        "annotations": {"episode_000000": annotation},
    }

    standard = to_standard_task_annotation(
        bundle,
        dataset_type=DatasetType.COROBOT,
        dataset_root="/data/task",
        primary_video_paths={"episode_000000": "/data/task/cam_top/episode_000000.mp4"},
    )

    assert standard["scene"]["objects"][0] == {
        "id": 0,
        "name": "block",
        "affordance": ["graspable"],
        "color": "red",
        "material": "wooden",
    }
    primary_action = standard["episode_annotation"][0]["subtasks"][0]["primary_action"]
    assert primary_action["slots"]["manipulated_object"] == object_ref
    assert primary_action["phases"][0]["object"] == object_ref


def test_task_export_deduplicates_skills_across_episodes():
    first = make_annotation("/data/task/cam_top/episode_000000.mp4")
    second = make_annotation("/data/task/cam_top/episode_000001.mp4")
    bundle = {
        "task": {
            "video_text": first["video_text"],
            "scene": first["scene"],
            "robot_setup": first["robot_setup"],
        },
        "annotations": {
            "episode_000000": first,
            "episode_000001": second,
        },
    }

    standard = to_standard_task_annotation(
        bundle,
        dataset_type=DatasetType.COROBOT,
        dataset_root="/data/task",
        primary_video_paths={
            "episode_000000": "/data/task/cam_top/episode_000000.mp4",
            "episode_000001": "/data/task/cam_top/episode_000001.mp4",
        },
    )

    assert len(standard["skills"]) == 1
    assert standard["episode_annotation"][0]["subtasks"][0]["skill_id"] == 0
    assert standard["episode_annotation"][1]["subtasks"][0]["skill_id"] == 0


def test_standard_import_rebuilds_subtask_text_from_actions():
    standard = {
        "task_description": "pour water",
        "task_type": "manipulation",
        "scene": {
            "scene_type": "table",
            "objects": [
                {"id": 0, "name": "cup", "affordance": ["receivable"]},
                {"id": 1, "name": "bottle", "affordance": ["pourable"]},
            ],
        },
        "robot_setup": {
            "base": {"mobility_type": "unknown"},
            "manipulators": [
                {"id": 0, "mount_position": "left", "end_effector_type": "two_finger"},
                {"id": 1, "mount_position": "right", "end_effector_type": "two_finger"},
            ],
        },
        "episode_annotation": [
            {
                "id": 0,
                "episode_video_path": "/data/task/cam_top/episode_000000.mp4",
                "frame_count": 20,
                "subtasks": [
                    {
                        "id": 0,
                        "start_frame": 0,
                        "end_frame": 20,
                        "state": "normal",
                        "coordination_mode": "primary_with_support",
                        "description": (
                            "left_effector pour liquid from bottle into cup by manipulating bottle "
                            "and affect cup, while right_effector hold cup to assist/support the primary action"
                        ),
                        "primary_action": {
                            "subject": "left_effector",
                            "skill": "pour",
                            "text": "left_effector pour liquid from bottle into cup by manipulating bottle and affect cup",
                            "slots": {
                                "substance": "liquid",
                                "source_container": "bottle",
                                "destination_container": "cup",
                                "manipulated_object": "bottle",
                                "changed_object": "cup",
                            },
                            "phases": [],
                        },
                        "auxiliary_action": {
                            "subject": "right_effector",
                            "skill": "hold",
                            "text": "right_effector hold cup",
                            "slots": {"interaction_target": "cup"},
                            "phases": [],
                        },
                    }
                ],
            }
        ],
    }

    annotation = annotation_from_standard_episode(
        standard,
        standard["episode_annotation"][0],
        {
            "episode_id": "episode_000000",
            "dataset_name": "Task",
            "video_path": "/data/task/cam_top/episode_000000.mp4",
            "primary_video_path": "/data/task/cam_top/episode_000000.mp4",
            "views": {"cam_top": "/data/task/cam_top/episode_000000.mp4"},
            "frames": 20,
        },
    )

    subtask = annotation["subtasks"][0]
    assert subtask["text"] == render_subtask_text(subtask["actions"])
    assert subtask["text"] == (
        "left_effector pour liquid from bottle into cup by manipulating bottle and affect cup; "
        "meanwhile right_effector hold cup"
    )
    assert subtask["_standard_subtask_entry"]["description"].endswith(
        "to assist/support the primary action"
    )


def test_task_export_preserves_existing_automatic_episodes_by_video_path():
    bundle = {
        "task": {
            "video_text": "put banana into basket",
            "scene": make_annotation("/data/task/cam_top/episode_000000.mp4")["scene"],
            "robot_setup": make_annotation("/data/task/cam_top/episode_000000.mp4")["robot_setup"],
        },
        "annotations": {
            "episode_000000": make_annotation("/data/task/cam_top/episode_000000.mp4"),
        },
    }
    existing_standard = {
        "version": "annotation_schema_v1",
        "episode_annotation": [
            {
                "id": 0,
                "episode_video_path": "/data/task/cam_top/episode_000001.mp4",
                "frame_count": 20,
                "annotation_meta": {"source": "automatic"},
                "subtasks": [
                    {
                        "id": 0,
                        "start_frame": 0,
                        "end_frame": 19,
                        "state": "normal",
                        "coordination_mode": "single_hand",
                        "description": "auto",
                        "primary_action": {
                            "subject": "right_effector",
                            "skill": "custom",
                            "text": "auto",
                            "slots": {},
                            "phases": [],
                        },
                    }
                ],
            }
        ],
    }

    standard = to_standard_task_annotation(
        bundle,
        dataset_type=DatasetType.COROBOT,
        dataset_root="/data/task",
        primary_video_paths={"episode_000000": "/data/task/cam_top/episode_000000.mp4"},
        existing_standard=existing_standard,
    )

    assert [item["id"] for item in standard["episode_annotation"]] == [0, 1]
    assert [
        item["episode_video_path"] for item in standard["episode_annotation"]
    ] == [
        "/data/task/cam_top/episode_000000.mp4",
        "/data/task/cam_top/episode_000001.mp4",
    ]
    assert standard["episode_annotation"][1]["annotation_meta"]["source"] == "automatic"


def test_standard_export_preserves_phases_for_reviewed_automatic_subtask_without_actions():
    existing_subtask = {
        "id": 0,
        "start_frame": 0,
        "end_frame": 20,
        "state": "normal",
        "coordination_mode": "single_hand",
        "description": "auto",
        "primary_action": {
            "subject": "right_effector",
            "skill": "custom",
            "text": "auto",
            "slots": {"description": "auto"},
            "phases": [],
        },
    }
    annotation = {
        "episode": {
            "episode_id": "episode_000000",
            "dataset_name": "Task",
            "video_path": "/data/task/cam_top/episode_000000.mp4",
            "primary_video_path": "/data/task/cam_top/episode_000000.mp4",
            "views": {"cam_top": "/data/task/cam_top/episode_000000.mp4"},
            "frames": 20,
        },
        "video_text": "auto task",
        "robot_setup": {},
        "scene": {},
        "subtasks": [
            {
                "start_frame": 0,
                "end_frame": 20,
                "state": "normal",
                "coordination_mode": "single_hand",
                "text": "auto",
                "actions": [],
                "phases": [
                    {
                        "target_action": "primary",
                        "start_frame": 0,
                        "end_frame": 20,
                        "action": "approach",
                        "object": "object",
                    }
                ],
                "_standard_subtask_entry": existing_subtask,
            }
        ],
    }

    standard = to_standard_task_annotation(
        {
            "task": {
                "video_text": annotation["video_text"],
                "scene": annotation["scene"],
                "robot_setup": annotation["robot_setup"],
            },
            "annotations": {"episode_000000": annotation},
        },
        dataset_type=DatasetType.LEROBOT,
        dataset_root="/data/task",
        primary_video_paths={"episode_000000": "/data/task/cam_top/episode_000000.mp4"},
        episode_order=["episode_000000"],
    )

    primary_action = standard["episode_annotation"][0]["subtasks"][0]["primary_action"]
    assert primary_action["phases"] == [
        {
            "id": 0,
            "start_frame": 0,
            "end_frame": 20,
            "action": "approach",
            "object": "object",
        }
    ]


def test_task_export_reads_common_record_from_meta_and_ignores_empty_annotations(tmp_path):
    dataset_root = tmp_path / "Task_Name_959"
    episode_root = dataset_root / "Task_Name_959_92715"
    meta_dir = episode_root / "meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "common_record.json").write_text(
        json.dumps(
            {
                "task_id": "959",
                "task_name": "Task Name",
                "machine_id": "machine_0",
            }
        ),
        encoding="utf-8",
    )
    video_path = episode_root / "videos/chunk-000/cam_top/episode_000000.mp4"
    bundle = {
        "task": {
            "video_text": "put banana into basket",
            "scene": make_annotation(str(video_path))["scene"],
            "robot_setup": make_annotation(str(video_path))["robot_setup"],
        },
        "annotations": {
            "annotated": make_annotation(str(video_path)),
            "opened_but_empty": {
                **make_annotation(str(video_path).replace("92715", "92716")),
                "subtasks": [],
            },
        },
    }

    standard = to_standard_task_annotation(
        bundle,
        dataset_type=DatasetType.COROBOT,
        dataset_root=dataset_root,
        primary_video_paths={"annotated": video_path},
        episode_order=["annotated", "opened_but_empty"],
    )

    assert standard["task_id"] == "959"
    assert standard["task_name"] == "Task Name"
    assert "machine_id" not in standard
    assert standard["data_path"] == str(dataset_root)
    assert len(standard["episode_annotation"]) == 1
    assert standard["episode_annotation"][0]["episode_video_path"] == str(video_path)


def test_find_standard_episode_falls_back_to_episode_file_name_when_roots_differ():
    standard_episode = {
        "episode_video_path": (
            "/home/user/franak_data/Franka_stack_block_0709_2473/videos/chunk-000/"
            "observation.images.image_wrist/episode_000004.mp4"
        ),
        "subtasks": [{"id": 0}],
    }
    standard = {
        "version": "annotation_schema_v1",
        "episode_annotation": [standard_episode],
    }
    episode = EpisodeItem(
        episode_id="episode_000004",
        display_name="episode_000004",
        annotation_stem="episode_000004",
        dataset_type=DatasetType.LEROBOT,
        dataset_root=Path("/media/liuyou/新加卷K/franka/proc/CoRobot/Franka_stack_block_0709_2473"),
        camera_videos={
            "observation.images.image_wrist": Path(
                "/media/liuyou/新加卷K/franka/proc/CoRobot/Franka_stack_block_0709_2473/"
                "videos/chunk-000/observation.images.image_wrist/episode_000004.mp4"
            ),
        },
        primary_video_path=Path(
            "/media/liuyou/新加卷K/franka/proc/CoRobot/Franka_stack_block_0709_2473/"
            "videos/chunk-000/observation.images.image_wrist/episode_000004.mp4"
        ),
    )

    assert find_standard_episode(standard, episode) is standard_episode


def test_find_standard_episode_matches_corobot_child_folder_when_episode_file_names_repeat():
    target = {
        "episode_video_path": (
            "/cloud/data/Agilex_Task_959/Agilex_Task_959_92716/"
            "videos/chunk-000/observation.images.image_top/episode_000000.mp4"
        ),
        "subtasks": [{"id": 0}],
    }
    standard = {
        "version": "annotation_schema_v1",
        "episode_annotation": [
            {
                "episode_video_path": (
                    "/cloud/data/Agilex_Task_959/Agilex_Task_959_92715/"
                    "videos/chunk-000/observation.images.image_top/episode_000000.mp4"
                ),
                "subtasks": [{"id": 0}],
            },
            target,
        ],
    }
    episode = EpisodeItem(
        episode_id="Agilex_Task_959_92716/episode_000000",
        display_name="Agilex_Task_959_92716/episode_000000",
        annotation_stem="Agilex_Task_959_92716__episode_000000",
        dataset_type=DatasetType.COROBOT,
        dataset_root=Path("/local/data/Agilex_Task_959/Agilex_Task_959_92716"),
        camera_videos={
            "observation.images.image_top": Path(
                "/local/data/Agilex_Task_959/Agilex_Task_959_92716/"
                "videos/chunk-000/observation.images.image_top/episode_000000.mp4"
            ),
        },
        primary_video_path=Path(
            "/local/data/Agilex_Task_959/Agilex_Task_959_92716/"
            "videos/chunk-000/observation.images.image_top/episode_000000.mp4"
        ),
    )

    assert find_standard_episode(standard, episode) is target


def test_find_standard_episode_does_not_fallback_to_repeated_corobot_episode_file_name():
    standard = {
        "version": "annotation_schema_v1",
        "episode_annotation": [
            {
                "episode_video_path": (
                    "/cloud/data/Galbot_Task_1054/Galbot_Task_1054_106231/"
                    "videos/chunk-000/observation.images.image_top/episode_000000.mp4"
                ),
                "subtasks": [{"id": 0}],
            }
        ],
    }
    episode = EpisodeItem(
        episode_id="Galbot_Task_1054_106232/episode_000000",
        display_name="Galbot_Task_1054_106232/episode_000000",
        annotation_stem="Galbot_Task_1054_106232__episode_000000",
        dataset_type=DatasetType.COROBOT,
        dataset_root=Path("/local/data/Galbot_Task_1054/Galbot_Task_1054_106232"),
        camera_videos={
            "observation.images.image_top": Path(
                "/local/data/Galbot_Task_1054/Galbot_Task_1054_106232/"
                "videos/chunk-000/observation.images.image_top/episode_000000.mp4"
            ),
        },
        primary_video_path=Path(
            "/local/data/Galbot_Task_1054/Galbot_Task_1054_106232/"
            "videos/chunk-000/observation.images.image_top/episode_000000.mp4"
        ),
    )

    assert find_standard_episode(standard, episode) is None


def test_find_standard_episode_returns_latest_duplicate_when_main_camera_changes():
    older = {
        "episode_video_path": "/cloud/task/videos/chunk-000/cam_top/episode_000000.mp4",
        "subtasks": [{"id": 0, "description": "older"}],
    }
    newer = {
        "episode_video_path": "/cloud/task/videos/chunk-000/cam_left/episode_000000.mp4",
        "subtasks": [{"id": 0, "description": "newer"}],
    }
    standard = {
        "version": "annotation_schema_v1",
        "episode_annotation": [older, newer],
    }
    episode = EpisodeItem(
        episode_id="episode_000000",
        display_name="episode_000000",
        annotation_stem="episode_000000",
        dataset_type=DatasetType.LEROBOT,
        dataset_root=Path("/local/task"),
        camera_videos={
            "cam_top": Path("/local/task/videos/chunk-000/cam_top/episode_000000.mp4"),
            "cam_left": Path("/local/task/videos/chunk-000/cam_left/episode_000000.mp4"),
        },
        primary_video_path=Path("/local/task/videos/chunk-000/cam_left/episode_000000.mp4"),
    )

    assert find_standard_episode(standard, episode) is newer


def test_episode_annotation_source_text_uses_annotation_meta_for_annotated_episode():
    assert episode_annotation_source_text({
        "annotation_meta": {"source": "vlm"},
        "subtasks": [{"id": 0}],
    }) == "VLM(vlm)"
    assert episode_annotation_source_text({
        "annotation_meta": {"source": "automatic"},
        "subtasks": [{"id": 0}],
    }) == "自动(automatic)"
    assert episode_annotation_source_text({
        "annotation_meta": {"source": "human"},
        "subtasks": [{"id": 0}],
    }) == "人工(human)"
    assert episode_annotation_source_text({
        "annotation_meta": {"source": "vlm"},
        "subtasks": [],
    }) == ""


def test_mark_annotation_human_reviewed_converts_auto_sources_to_hybrid():
    auto_annotation = {"annotation_meta": {"source": "automatic", "model_name": "model"}}
    vlm_annotation = {"annotation_meta": {"source": "vlm"}}
    human_annotation = {"annotation_meta": {"source": "human"}}
    hybrid_annotation = {"annotation_meta": {"source": "hybrid"}}
    missing_meta_annotation = {}

    mark_annotation_human_reviewed(auto_annotation)
    mark_annotation_human_reviewed(vlm_annotation)
    mark_annotation_human_reviewed(human_annotation)
    mark_annotation_human_reviewed(hybrid_annotation)
    mark_annotation_human_reviewed(missing_meta_annotation)

    assert auto_annotation["annotation_meta"] == {"source": "hybrid", "model_name": "model"}
    assert vlm_annotation["annotation_meta"]["source"] == "hybrid"
    assert human_annotation["annotation_meta"]["source"] == "human"
    assert hybrid_annotation["annotation_meta"]["source"] == "hybrid"
    assert missing_meta_annotation["annotation_meta"]["source"] == "human"


def test_standard_round_trip_preserves_automatic_fields_when_episode_is_edited():
    existing_standard = {
        "version": "annotation_schema_v1",
        "annotation_spec_version": "skill_spec_v1",
        "task_id": "959",
        "task_name": "Task Name",
        "task_type": "object_rearrangement",
        "data_type": "lerobot2.1",
        "data_path": "/cloud/dataset",
        "cameras": [{"id": 0, "name": "cam_top", "role": "primary"}],
        "task_description": "move object",
        "robot_setup": {
            "base": {"mobility_type": "unknown"},
            "manipulators": [
                {"id": 0, "mount_position": "right", "end_effector_type": "two_finger"}
            ],
        },
        "scene": {
            "scene_type": "table",
            "objects": [{"id": 0, "name": "object", "affordance": ["graspable"]}],
        },
        "top_level_vlm_field": {"keep": True},
        "episode_annotation": [
            {
                "id": 0,
                "episode_video_path": "/cloud/dataset/videos/chunk-000/cam_top/episode_000000.mp4",
                "frame_count": 20,
                "annotation_meta": {"source": "automatic", "model_name": "auto_model"},
                "episode_prediction_meta": {"keep": "episode"},
                "subtasks": [
                    {
                        "id": 0,
                        "start_frame": 0,
                        "end_frame": 20,
                        "state": "normal",
                        "coordination_mode": "single_hand",
                        "description": "right_effector manipulate object",
                        "subtask_prediction_meta": {"alignment_score": 0.9},
                        "review_flags": ["boundary_ambiguous"],
                        "primary_action": {
                            "subject": "right_effector",
                            "skill": "custom",
                            "text": "right_effector manipulate object",
                            "slots": {"description": "manipulate object"},
                            "action_prediction_meta": {"keep": "action"},
                            "phases": [
                                {
                                    "id": 0,
                                    "start_frame": 0,
                                    "end_frame": 20,
                                    "action": "approach",
                                    "object": "object",
                                    "phases_prediction_meta": {"alignment_score": 0.8},
                                    "phase_review": "keep",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    episode_metadata = {
        "episode_id": "episode_000000",
        "dataset_name": "Task_Name_959",
        "video_path": "/local/dataset/videos/chunk-000/cam_top/episode_000000.mp4",
        "primary_video_path": "/local/dataset/videos/chunk-000/cam_top/episode_000000.mp4",
        "views": {"cam_top": "/local/dataset/videos/chunk-000/cam_top/episode_000000.mp4"},
        "frames": 20,
    }
    annotation = annotation_from_standard_episode(
        existing_standard,
        existing_standard["episode_annotation"][0],
        episode_metadata,
    )
    annotation["subtasks"][0]["end_frame"] = 19

    standard = to_standard_task_annotation(
        {
            "task": {
                "video_text": annotation["video_text"],
                "scene": annotation["scene"],
                "robot_setup": annotation["robot_setup"],
            },
            "annotations": {"episode_000000": annotation},
        },
        dataset_type=DatasetType.LEROBOT,
        dataset_root="/local/dataset",
        primary_video_paths={
            "episode_000000": "/local/dataset/videos/chunk-000/cam_top/episode_000000.mp4"
        },
        episode_order=["episode_000000"],
        existing_standard=existing_standard,
    )

    assert standard["top_level_vlm_field"] == {"keep": True}
    assert len(standard["episode_annotation"]) == 1
    episode = standard["episode_annotation"][0]
    assert episode["episode_prediction_meta"] == {"keep": "episode"}
    assert episode["episode_video_path"] == "/local/dataset/videos/chunk-000/cam_top/episode_000000.mp4"
    subtask = episode["subtasks"][0]
    assert subtask["end_frame"] == 19
    assert subtask["subtask_prediction_meta"] == {"alignment_score": 0.9}
    assert subtask["review_flags"] == ["boundary_ambiguous"]
    action = subtask["primary_action"]
    assert action["action_prediction_meta"] == {"keep": "action"}
    phase = action["phases"][0]
    assert phase["phases_prediction_meta"] == {"alignment_score": 0.8}
    assert phase["phase_review"] == "keep"


def test_standard_export_replaces_existing_episode_in_place():
    existing_standard = {
        "version": "annotation_schema_v1",
        "episode_annotation": [
            {
                "id": 0,
                "episode_video_path": "/cloud/task/cam_top/episode_000000.mp4",
                "frame_count": 20,
                "annotation_meta": {"source": "automatic"},
                "subtasks": [
                    {
                        "id": 0,
                        "start_frame": 0,
                        "end_frame": 20,
                        "state": "normal",
                        "coordination_mode": "single_hand",
                        "description": "auto 0",
                        "primary_action": {
                            "subject": "right_effector",
                            "skill": "custom",
                            "text": "auto 0",
                            "slots": {"description": "auto 0"},
                            "phases": [],
                        },
                    }
                ],
            },
            {
                "id": 1,
                "episode_video_path": "/cloud/task/cam_top/episode_000001.mp4",
                "frame_count": 20,
                "annotation_meta": {"source": "automatic"},
                "subtasks": [
                    {
                        "id": 0,
                        "start_frame": 0,
                        "end_frame": 20,
                        "state": "normal",
                        "coordination_mode": "single_hand",
                        "description": "auto 1",
                        "primary_action": {
                            "subject": "right_effector",
                            "skill": "custom",
                            "text": "auto 1",
                            "slots": {"description": "auto 1"},
                            "phases": [],
                        },
                    }
                ],
            },
        ],
    }
    annotation = make_annotation("/local/task/cam_top/episode_000001.mp4", frames=20)
    annotation["_standard_episode_entry"] = existing_standard["episode_annotation"][1]
    annotation["subtasks"][0]["end_frame"] = 20

    standard = to_standard_task_annotation(
        {
            "task": {
                "video_text": annotation["video_text"],
                "scene": annotation["scene"],
                "robot_setup": annotation["robot_setup"],
            },
            "annotations": {"episode_000001": annotation},
        },
        dataset_type=DatasetType.LEROBOT,
        dataset_root="/local/task",
        primary_video_paths={"episode_000001": "/local/task/cam_top/episode_000001.mp4"},
        episode_order=["episode_000001"],
        existing_standard=existing_standard,
    )

    assert [
        item["episode_video_path"] for item in standard["episode_annotation"]
    ] == [
        "/cloud/task/cam_top/episode_000000.mp4",
        "/local/task/cam_top/episode_000001.mp4",
    ]
    assert [item["id"] for item in standard["episode_annotation"]] == [0, 1]
    assert standard["episode_annotation"][0]["subtasks"][0]["description"] == "auto 0"


def test_standard_export_replaces_existing_episode_when_primary_camera_changes():
    existing_standard = {
        "version": "annotation_schema_v1",
        "episode_annotation": [
            {
                "id": 0,
                "episode_video_path": "/cloud/task/cam_top/episode_000000.mp4",
                "frame_count": 20,
                "annotation_meta": {"source": "automatic"},
                "subtasks": [
                    {
                        "id": 0,
                        "start_frame": 0,
                        "end_frame": 20,
                        "state": "normal",
                        "coordination_mode": "single_hand",
                        "description": "auto 0",
                        "primary_action": {
                            "subject": "right_effector",
                            "skill": "custom",
                            "text": "auto 0",
                            "slots": {"description": "auto 0"},
                            "phases": [],
                        },
                    }
                ],
            }
        ],
    }
    annotation = make_annotation("/local/task/cam_left/episode_000000.mp4", frames=20)
    annotation["episode"]["views"] = {
        "cam_top": "/local/task/cam_top/episode_000000.mp4",
        "cam_left": "/local/task/cam_left/episode_000000.mp4",
    }
    annotation["subtasks"][0]["actions"][0]["text"] = "human corrected"

    standard = to_standard_task_annotation(
        {
            "task": {
                "video_text": annotation["video_text"],
                "scene": annotation["scene"],
                "robot_setup": annotation["robot_setup"],
            },
            "annotations": {"episode_000000": annotation},
        },
        dataset_type=DatasetType.LEROBOT,
        dataset_root="/local/task",
        primary_video_paths={"episode_000000": "/local/task/cam_left/episode_000000.mp4"},
        episode_order=["episode_000000"],
        existing_standard=existing_standard,
    )

    assert len(standard["episode_annotation"]) == 1
    assert standard["episode_annotation"][0]["episode_video_path"] == "/local/task/cam_left/episode_000000.mp4"
    assert standard["episode_annotation"][0]["subtasks"][0]["description"] == "human corrected"


def test_standard_export_deduplicates_existing_episode_entries_by_episode_identity():
    existing_standard = {
        "version": "annotation_schema_v1",
        "episode_annotation": [
            {
                "id": 0,
                "episode_video_path": "/cloud/task/cam_top/episode_000000.mp4",
                "frame_count": 20,
                "annotation_meta": {"source": "human"},
                "subtasks": [
                    {
                        "id": 0,
                        "start_frame": 0,
                        "end_frame": 20,
                        "state": "normal",
                        "coordination_mode": "single_hand",
                        "description": "older",
                        "primary_action": {
                            "subject": "right_effector",
                            "skill": "custom",
                            "text": "older",
                            "slots": {"description": "older"},
                            "phases": [],
                        },
                    }
                ],
            },
            {
                "id": 1,
                "episode_video_path": "/cloud/task/cam_left/episode_000000.mp4",
                "frame_count": 20,
                "annotation_meta": {"source": "human"},
                "subtasks": [
                    {
                        "id": 0,
                        "start_frame": 0,
                        "end_frame": 20,
                        "state": "normal",
                        "coordination_mode": "single_hand",
                        "description": "newer",
                        "primary_action": {
                            "subject": "right_effector",
                            "skill": "custom",
                            "text": "newer",
                            "slots": {"description": "newer"},
                            "phases": [],
                        },
                    }
                ],
            },
        ],
    }

    standard = to_standard_task_annotation(
        {"task": {}, "annotations": {}},
        dataset_type=DatasetType.LEROBOT,
        dataset_root="/local/task",
        existing_standard=existing_standard,
    )

    assert len(standard["episode_annotation"]) == 1
    assert standard["episode_annotation"][0]["id"] == 0
    assert standard["episode_annotation"][0]["subtasks"][0]["description"] == "newer"
