from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def backup(path: Path) -> None:
    if not path.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(path, path.with_name(f"{path.stem}.before_half_open_{stamp}{path.suffix}"))


def is_closed_interval_sequence(subtasks: list[dict[str, Any]]) -> bool:
    if len(subtasks) < 2:
        return False
    for previous, current in zip(subtasks, subtasks[1:]):
        if int(current.get("start_frame", -1)) != int(previous.get("end_frame", -1)) + 1:
            return False
    return True


def convert_ranges_in_subtasks(subtasks: list[dict[str, Any]]) -> int:
    changed = 0
    if not is_closed_interval_sequence(subtasks):
        return changed
    for subtask in subtasks:
        subtask["end_frame"] = int(subtask["end_frame"]) + 1
        changed += 1
        phases = subtask.get("phases") or []
        if is_closed_interval_sequence(phases):
            for phase in phases:
                phase["end_frame"] = int(phase["end_frame"]) + 1
    return changed


def convert_ranges_in_standard_subtasks(subtasks: list[dict[str, Any]]) -> int:
    changed = 0
    if not is_closed_interval_sequence(subtasks):
        return changed
    for subtask in subtasks:
        subtask["end_frame"] = int(subtask["end_frame"]) + 1
        changed += 1
        for action_key in ("primary_action", "auxiliary_action"):
            action = subtask.get(action_key)
            if not isinstance(action, dict):
                continue
            phases = action.get("phases") or []
            if is_closed_interval_sequence(phases):
                for phase in phases:
                    phase["end_frame"] = int(phase["end_frame"]) + 1
    return changed


def convert_annotation_bundle(path: Path, dry_run: bool) -> tuple[int, int]:
    data = load_json(path)
    changed_episodes = 0
    changed_subtasks = 0
    for annotation in data.get("annotations", {}).values():
        if not isinstance(annotation, dict):
            continue
        changed = convert_ranges_in_subtasks(annotation.get("subtasks") or [])
        if changed:
            changed_episodes += 1
            changed_subtasks += changed
    if changed_subtasks and not dry_run:
        backup(path)
        dump_json(path, data)
    return changed_episodes, changed_subtasks


def convert_standard_file(path: Path, dry_run: bool) -> tuple[int, int]:
    data = load_json(path)
    changed_episodes = 0
    changed_subtasks = 0
    for episode in data.get("episode_annotation") or []:
        if not isinstance(episode, dict):
            continue
        changed = convert_ranges_in_standard_subtasks(episode.get("subtasks") or [])
        if changed:
            changed_episodes += 1
            changed_subtasks += changed
    if changed_subtasks and not dry_run:
        backup(path)
        dump_json(path, data)
    return changed_episodes, changed_subtasks


def convert_root(raw_root: Path, dry_run: bool) -> None:
    total_episodes = 0
    total_subtasks = 0
    for dataset_dir in sorted(path for path in raw_root.iterdir() if path.is_dir()):
        annotation_path = dataset_dir / "lite_annotations" / "annotations.json"
        standard_path = dataset_dir / "lite_annotations" / "annotation_schema_v1.json"
        dataset_episodes = 0
        dataset_subtasks = 0
        if annotation_path.exists():
            episodes, subtasks = convert_annotation_bundle(annotation_path, dry_run)
            dataset_episodes += episodes
            dataset_subtasks += subtasks
        if standard_path.exists():
            convert_standard_file(standard_path, dry_run)
        if dataset_episodes or dataset_subtasks:
            print(
                f"{dataset_dir.name}: converted_episodes={dataset_episodes}, "
                f"converted_subtasks={dataset_subtasks}"
            )
        total_episodes += dataset_episodes
        total_subtasks += dataset_subtasks
    mode = "DRY RUN" if dry_run else "WROTE FILES"
    print(f"{mode}: converted_episodes={total_episodes}, converted_subtasks={total_subtasks}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert legacy closed frame intervals to half-open intervals.")
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    convert_root(args.raw_root.expanduser().resolve(), args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
