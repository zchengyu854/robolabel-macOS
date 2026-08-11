from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lite_annotator.annotation_store import default_annotation_file
from lite_annotator.dataset_loader import DatasetType
from lite_annotator.skill_library import skill_library_path
from lite_annotator.standard_export import (
    STANDARD_FILE_NAME,
    standard_annotation_path,
    to_standard_task_annotation,
)


CAMERA_ALIASES = {
    "observation_images_image_left": "observation.images.image_left",
    "observation_images_image_right": "observation.images.image_right",
    "observation_images_image_top": "observation.images.image_top",
}


@dataclass
class DatasetImportResult:
    legacy_dir: Path
    raw_dir: Path | None = None
    found_files: int = 0
    imported_files: int = 0
    skipped_files: int = 0
    warnings: list[str] = field(default_factory=list)


def normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def strip_legacy_prefix(name: str) -> str:
    return name[len("lerobot_"):] if name.startswith("lerobot_") else name


def match_raw_dataset(legacy_dir: Path, raw_root: Path) -> Path | None:
    target = strip_legacy_prefix(legacy_dir.name)
    raw_dirs = [path for path in raw_root.iterdir() if path.is_dir()]
    by_exact = {path.name: path for path in raw_dirs}
    if target in by_exact:
        return by_exact[target]

    target_norm = normalized_name(target)
    scored = []
    for raw_dir in raw_dirs:
        raw_norm = normalized_name(raw_dir.name)
        if target_norm and (target_norm in raw_norm or raw_norm in target_norm):
            scored.append((abs(len(raw_norm) - len(target_norm)), raw_dir))
    if scored:
        return sorted(scored, key=lambda item: (item[0], item[1].name))[0][1]
    return None


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def backup_if_exists(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.stem}.before_legacy_import_{stamp}{path.suffix}")
    shutil.copy2(path, backup_path)


def episode_name_from_legacy_path(path: Path) -> str:
    match = re.search(r"(episode_\d+)", path.stem)
    return match.group(1) if match else path.stem


def chunk_name_from_legacy_path(path: Path) -> str:
    match = re.search(r"(chunk-\d+)", path.stem)
    return match.group(1) if match else "chunk-000"


def normalize_camera_name(value: str) -> str:
    return normalized_name(value.replace("observation_images_", "observation.images."))


def camera_alias(value: str) -> str:
    return CAMERA_ALIASES.get(value, value.replace("observation_images_", "observation.images."))


def raw_camera_dirs(raw_dir: Path, chunk_name: str) -> list[Path]:
    chunk_dir = raw_dir / "videos" / chunk_name
    if not chunk_dir.exists():
        return []
    return sorted(path for path in chunk_dir.iterdir() if path.is_dir())


def build_views(raw_dir: Path, legacy_annotation: dict[str, Any], legacy_path: Path) -> tuple[dict[str, str], str | None]:
    episode_name = episode_name_from_legacy_path(legacy_path)
    chunk_name = chunk_name_from_legacy_path(legacy_path)
    camera_dirs = raw_camera_dirs(raw_dir, chunk_name)
    views = {}
    for camera_dir in camera_dirs:
        video_path = camera_dir / f"{episode_name}.mp4"
        if video_path.exists():
            views[camera_dir.name] = str(video_path)

    old_episode = legacy_annotation.get("episode") or {}
    old_primary_path = str(old_episode.get("primary_video_path") or old_episode.get("video_path") or "")
    old_primary_camera = Path(old_primary_path).stem
    for camera in (old_episode.get("views") or {}):
        if str(old_episode.get("views", {}).get(camera, "")) == old_primary_path:
            old_primary_camera = camera
            break
    target_camera = camera_alias(old_primary_camera)
    target_norm = normalize_camera_name(target_camera)
    primary = None
    for camera, path in views.items():
        if normalize_camera_name(camera) == target_norm:
            primary = path
            break
    if primary is None and views:
        primary = views[sorted(views)[0]]
    return views, primary


def normalize_robot_setup(robot_setup: dict[str, Any] | None) -> dict[str, Any]:
    robot_setup = dict(robot_setup or {})
    robot_setup.setdefault("embodiment", "dual_arm")
    robot_setup.setdefault("base_mobility_type", "unknown")
    if "single_effector_type" not in robot_setup:
        robot_setup.setdefault("left_effector_type", "two_finger")
        robot_setup.setdefault("right_effector_type", "two_finger")
    return robot_setup


def normalize_subtasks(
    subtasks: list[dict[str, Any]],
    skill_ids: dict[str, str],
) -> list[dict[str, Any]]:
    result = []
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        item = dict(subtask)
        item.setdefault("state", "normal")
        item.setdefault("phases", [])
        text = str(item.get("text", "")).strip()
        key = json.dumps(
            {
                "coordination_mode": item.get("coordination_mode", "single_hand"),
                "actions": item.get("actions") or [],
                "text": text,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        item["skill_id"] = skill_ids[key]
        result.append(item)
    return result


def collect_skill_templates(legacy_annotations: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, Any]]:
    skill_ids: dict[str, str] = {}
    skills = []
    for annotation in legacy_annotations:
        for subtask in annotation.get("subtasks") or []:
            if not isinstance(subtask, dict):
                continue
            text = str(subtask.get("text", "")).strip()
            template = {
                "coordination_mode": subtask.get("coordination_mode", "single_hand"),
                "actions": subtask.get("actions") or [],
                "text": text,
            }
            key = json.dumps(template, ensure_ascii=False, sort_keys=True)
            if key in skill_ids:
                continue
            skill_id = f"legacy_skill_{len(skills):06d}"
            skill_ids[key] = skill_id
            skills.append({
                "id": skill_id,
                "text": text,
                "template": template,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "source": "legacy_human_anno_lang",
            })
    return skill_ids, {"version": 1, "skills": skills}


def convert_annotation(
    raw_dir: Path,
    legacy_annotation: dict[str, Any],
    legacy_path: Path,
    skill_ids: dict[str, str],
) -> dict[str, Any] | None:
    views, primary = build_views(raw_dir, legacy_annotation, legacy_path)
    if not views or primary is None:
        return None

    episode_name = episode_name_from_legacy_path(legacy_path)
    annotation = dict(legacy_annotation)
    annotation["robot_setup"] = normalize_robot_setup(annotation.get("robot_setup"))
    annotation["subtasks"] = normalize_subtasks(annotation.get("subtasks") or [], skill_ids)
    episode = dict(annotation.get("episode") or {})
    episode.update({
        "episode_id": episode_name,
        "task_id": episode_name,
        "dataset_name": raw_dir.name,
        "video_path": primary,
        "primary_video_path": primary,
        "views": views,
    })
    annotation["episode"] = episode
    return annotation


def import_dataset(legacy_dir: Path, raw_root: Path, dry_run: bool) -> DatasetImportResult:
    result = DatasetImportResult(legacy_dir=legacy_dir)
    raw_dir = match_raw_dataset(legacy_dir, raw_root)
    result.raw_dir = raw_dir
    if raw_dir is None:
        result.warnings.append("未找到匹配的原始数据目录")
        return result

    annotation_paths = sorted((legacy_dir / "human_anno_lang").glob("*.json"))
    result.found_files = len(annotation_paths)
    legacy_annotations = []
    for path in annotation_paths:
        try:
            legacy_annotations.append(load_json(path))
        except (OSError, json.JSONDecodeError) as exc:
            result.skipped_files += 1
            result.warnings.append(f"{path.name}: 读取失败: {exc}")

    skill_ids, skill_library = collect_skill_templates(legacy_annotations)
    annotations = {}
    for path, legacy_annotation in zip(annotation_paths, legacy_annotations):
        converted = convert_annotation(raw_dir, legacy_annotation, path, skill_ids)
        if converted is None:
            result.skipped_files += 1
            result.warnings.append(f"{path.name}: 找不到对应视频")
            continue
        key = episode_name_from_legacy_path(path)
        annotations[key] = converted
        result.imported_files += 1

    if not dry_run and annotations:
        annotation_file = default_annotation_file(raw_dir)
        skill_file = skill_library_path(raw_dir)
        standard_file = standard_annotation_path(raw_dir)
        for path in (annotation_file, skill_file, standard_file):
            backup_if_exists(path)
        first_annotation = next(iter(annotations.values()))
        bundle = {
            "version": 1,
            "task": {
                "video_text": first_annotation.get("video_text", ""),
                "scene": first_annotation.get("scene"),
                "robot_setup": first_annotation.get("robot_setup"),
            },
            "annotations": annotations,
        }
        dump_json(annotation_file, bundle)
        dump_json(skill_file, skill_library)
        standard = to_standard_task_annotation(
            bundle,
            dataset_type=DatasetType.LEROBOT,
            dataset_root=raw_dir,
            primary_video_paths={
                key: annotation.get("episode", {}).get("primary_video_path", "")
                for key, annotation in annotations.items()
            },
            episode_order=sorted(annotations),
        )
        dump_json(standard_file, standard)

    return result


def iter_legacy_dirs(legacy_root: Path) -> list[Path]:
    return sorted(
        path for path in legacy_root.iterdir()
        if path.is_dir() and (path / "human_anno_lang").is_dir()
    )


def print_result(result: DatasetImportResult) -> None:
    raw = str(result.raw_dir) if result.raw_dir else "未匹配"
    print(
        f"{result.legacy_dir.name} -> {raw}: "
        f"found={result.found_files}, imported={result.imported_files}, skipped={result.skipped_files}"
    )
    for warning in result.warnings[:10]:
        print(f"  warning: {warning}")
    if len(result.warnings) > 10:
        print(f"  warning: ... {len(result.warnings) - 10} more")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import legacy human_anno_lang annotations into robolabel format.")
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--legacy-root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    raw_root = args.raw_root.expanduser().resolve()
    legacy_root = args.legacy_root.expanduser().resolve()
    if not raw_root.exists():
        parser.error(f"raw root not found: {raw_root}")
    if not legacy_root.exists():
        parser.error(f"legacy root not found: {legacy_root}")

    totals = {"found": 0, "imported": 0, "skipped": 0}
    for legacy_dir in iter_legacy_dirs(legacy_root):
        result = import_dataset(legacy_dir, raw_root, args.dry_run)
        print_result(result)
        totals["found"] += result.found_files
        totals["imported"] += result.imported_files
        totals["skipped"] += result.skipped_files

    mode = "DRY RUN" if args.dry_run else "WROTE FILES"
    print(
        f"{mode}: datasets={len(iter_legacy_dirs(legacy_root))}, "
        f"found={totals['found']}, imported={totals['imported']}, skipped={totals['skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
