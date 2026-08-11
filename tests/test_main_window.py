from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QAbstractItemView, QHeaderView

from lite_annotator.dataset_loader import DatasetType, EpisodeItem
from lite_annotator.main_window import MainWindow

_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication([])
    return _APP


def test_episode_table_allows_horizontal_scrolling_for_long_episode_names():
    app()

    window = MainWindow()

    assert window.video_list.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert window.video_list.horizontalScrollMode() == QAbstractItemView.ScrollPerPixel
    assert window.video_list.horizontalHeader().sectionResizeMode(2) == QHeaderView.Interactive


def test_load_saved_annotation_prefers_reviewed_bundle_over_standard_export(tmp_path):
    app()
    dataset_root = tmp_path / "dataset"
    annotation_dir = dataset_root / "lite_annotations"
    annotation_dir.mkdir(parents=True)
    video_path = dataset_root / "videos" / "chunk-000" / "cam_top" / "episode_000000.mp4"

    bundle_annotation = {
        "episode": {
            "episode_id": "episode_000000",
            "dataset_name": "dataset",
            "video_path": str(video_path),
            "primary_video_path": str(video_path),
            "views": {"cam_top": str(video_path)},
            "frames": 20,
        },
        "video_text": "reviewed task",
        "robot_setup": {},
        "scene": {},
        "subtasks": [
            {
                "start_frame": 0,
                "end_frame": 20,
                "state": "normal",
                "coordination_mode": "single_hand",
                "actions": [],
                "text": "reviewed",
                "phases": [
                    {
                        "target_action": "primary",
                        "start_frame": 0,
                        "end_frame": 20,
                        "action": "approach",
                        "object": "object",
                    }
                ],
            }
        ],
    }
    standard_annotation = {
        "version": "annotation_schema_v1",
        "task_description": "automatic task",
        "robot_setup": {},
        "scene": {},
        "episode_annotation": [
            {
                "id": 0,
                "episode_video_path": str(video_path),
                "frame_count": 20,
                "annotation_meta": {"source": "automatic"},
                "subtasks": [
                    {
                        "id": 0,
                        "start_frame": 0,
                        "end_frame": 20,
                        "state": "normal",
                        "coordination_mode": "single_hand",
                        "description": "automatic",
                        "primary_action": {
                            "subject": "right_effector",
                            "skill": "custom",
                            "text": "automatic",
                            "slots": {},
                            "phases": [],
                        },
                    }
                ],
            }
        ],
    }
    (annotation_dir / "annotations.json").write_text(
        json.dumps(
            {
                "version": 1,
                "task": {"video_text": "", "scene": None, "robot_setup": None},
                "annotations": {"episode_000000": bundle_annotation},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (annotation_dir / "annotation_schema_v1.json").write_text(
        json.dumps(standard_annotation, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    window = MainWindow()
    window.dataset_root = dataset_root
    window.current_video_path = video_path
    window.current_episode = EpisodeItem(
        episode_id="episode_000000",
        display_name="episode_000000",
        annotation_stem="episode_000000",
        dataset_type=DatasetType.LEROBOT,
        dataset_root=dataset_root,
        camera_videos={"cam_top": video_path},
        primary_video_path=video_path,
    )

    annotation = window.load_saved_annotation("episode_000000")

    assert annotation["video_text"] == "reviewed task"
    assert annotation["subtasks"][0]["phases"] == bundle_annotation["subtasks"][0]["phases"]
