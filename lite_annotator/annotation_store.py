from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lite_annotator.annotation_model import normalize_annotation

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def scan_video_files(video_dir: str | Path) -> list[Path]:
    root = Path(video_dir)
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def default_annotation_dir(dataset_root: str | Path) -> Path:
    return Path(dataset_root) / "lite_annotations"


def default_annotation_file(dataset_root: str | Path) -> Path:
    return default_annotation_dir(dataset_root) / "annotations.json"


def empty_annotation_bundle() -> dict[str, Any]:
    return {
        "version": 1,
        "task": {"video_text": "", "scene": None, "robot_setup": None},
        "annotations": {},
    }


def load_annotation_bundle(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return empty_annotation_bundle()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("version", 1)
    data.setdefault("task", {"video_text": "", "scene": None, "robot_setup": None})
    data["task"].setdefault("video_text", "")
    data["task"].setdefault("scene", None)
    data["task"].setdefault("robot_setup", None)
    data.setdefault("annotations", {})
    return data


def load_annotation_from_bundle(path: str | Path, key: str) -> dict[str, Any] | None:
    bundle = load_annotation_bundle(path)
    annotation = bundle.get("annotations", {}).get(key)
    return normalize_annotation(annotation) if annotation else None


def load_annotation_bundle_keys(path: str | Path) -> list[str]:
    bundle = load_annotation_bundle(path)
    return sorted(str(key) for key in bundle.get("annotations", {}))


def load_annotated_episode_keys(path: str | Path) -> list[str]:
    bundle = load_annotation_bundle(path)
    return sorted(
        str(key)
        for key, annotation in bundle.get("annotations", {}).items()
        if isinstance(annotation, dict) and annotation.get("subtasks")
    )


def load_shared_task_fields(path: str | Path) -> dict[str, Any]:
    bundle = load_annotation_bundle(path)
    task = bundle.get("task") or {}
    return {
        "video_text": str(task.get("video_text", "")),
        "scene": task.get("scene"),
        "robot_setup": task.get("robot_setup"),
    }


def save_shared_task_fields(path: str | Path, task_fields: dict[str, Any]) -> None:
    path = Path(path)
    bundle = load_annotation_bundle(path)
    bundle["task"] = {
        "video_text": str(task_fields.get("video_text", "")),
        "scene": task_fields.get("scene"),
        "robot_setup": task_fields.get("robot_setup"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)


def save_annotation_to_bundle(path: str | Path, key: str, annotation: dict[str, Any]) -> None:
    path = Path(path)
    bundle = load_annotation_bundle(path)
    bundle["annotations"][key] = annotation
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
