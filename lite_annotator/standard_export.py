from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from common.skill_schema import render_subtask_text
from lite_annotator.annotation_model import create_empty_annotation
from lite_annotator.annotation_store import default_annotation_dir
from lite_annotator.dataset_loader import DatasetType, EpisodeItem

STANDARD_VERSION = "annotation_schema_v1"
ANNOTATION_SPEC_VERSION = "skill_spec_v1"
STANDARD_FILE_NAME = "annotation_schema_v1.json"


def standard_annotation_path(dataset_root: str | Path, annotation_stem: str | None = None) -> Path:
    if annotation_stem:
        return default_annotation_dir(dataset_root) / f"{annotation_stem}_standard.json"
    return default_annotation_dir(dataset_root) / STANDARD_FILE_NAME


def normalized_data_type(dataset_type) -> str:
    value = str(getattr(dataset_type, "value", dataset_type) or "")
    if value == DatasetType.LEROBOT.value:
        return "lerobot2.1"
    if value == DatasetType.COROBOT.value:
        return "corobot"
    return value or "unknown"


def parse_episode_index(episode_id: str) -> int:
    matches = re.findall(r"(\d+)", str(episode_id or ""))
    return int(matches[-1]) if matches else 0


def split_task_from_dataset_name(dataset_name: str) -> tuple[str, str]:
    text = str(dataset_name or "")
    match = re.match(r"(.+)_([0-9]+)$", text)
    if not match:
        return text, ""
    return match.group(1), match.group(2)


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_standard_task_file(path: str | Path) -> dict[str, Any]:
    data = read_json_file(Path(path))
    if data.get("version") != STANDARD_VERSION:
        return {}
    data.setdefault("episode_annotation", [])
    return data


def episode_identity_from_path(path: str | Path | None) -> str:
    path_text = str(path or "").strip()
    if not path_text:
        return ""
    video_path = Path(path_text)
    stem = video_path.stem
    if not stem:
        return ""
    parts = video_path.parts
    if "videos" in parts:
        videos_index = parts.index("videos")
        if videos_index > 0:
            return f"{parts[videos_index - 1]}/{stem}"
    return stem


def episode_identities_from_paths(paths: list[str | Path | None] | set[str | Path | None]) -> set[str]:
    return {
        identity
        for identity in (episode_identity_from_path(path) for path in paths)
        if identity
    }


def annotation_episode_identities(
    annotation: dict[str, Any],
    primary_video_path: str | Path | None = None,
    annotation_key: str | None = None,
) -> set[str]:
    episode = annotation.get("episode") if isinstance(annotation.get("episode"), dict) else {}
    accepted_stems = {
        Path(str(path)).stem
        for path in (
            primary_video_path,
            episode.get("primary_video_path"),
            episode.get("video_path"),
        )
        if str(path or "").strip()
    }
    if annotation_key:
        key = str(annotation_key)
        accepted_stems.add(key.rsplit("__", 1)[-1])
    paths = [
        primary_video_path,
        episode.get("primary_video_path"),
        episode.get("video_path"),
    ]
    views = episode.get("views") if isinstance(episode.get("views"), dict) else {}
    paths.extend(
        path
        for path in views.values()
        if not accepted_stems or Path(str(path)).stem in accepted_stems
    )
    identities = episode_identities_from_paths(paths)
    episode_id = str(episode.get("episode_id") or "").strip()
    episode_stem = episode_id.split("/")[-1]
    if episode_id and "/" in episode_id and (not accepted_stems or episode_stem in accepted_stems):
        identities.add(episode_id)
    dataset_name = str(episode.get("dataset_name") or "").strip()
    if dataset_name and episode_id and (not accepted_stems or episode_stem in accepted_stems):
        identities.add(f"{dataset_name}/{episode_id.split('/')[-1]}")
    if annotation_key:
        key = str(annotation_key)
        if "__" in key:
            dataset, episode_name = key.rsplit("__", 1)
            identities.add(f"{dataset}/{episode_name}")
        elif key:
            identities.add(key)
    return identities


def standard_episode_identities(item: dict[str, Any]) -> set[str]:
    identities = episode_identities_from_paths({item.get("episode_video_path")})
    episode_identity = str(item.get("episode_identity") or "").strip()
    if episode_identity:
        identities.add(episode_identity)
    return identities


def dedupe_standard_episode_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_by_identity: dict[str, int] = {}
    selected: list[dict[str, Any] | None] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("subtasks"):
            continue
        identities = standard_episode_identities(item)
        duplicate_indexes = {
            selected_by_identity[identity]
            for identity in identities
            if identity in selected_by_identity
        }
        if duplicate_indexes:
            keep_index = min(duplicate_indexes)
            selected[keep_index] = item
            for index in duplicate_indexes:
                if index != keep_index:
                    selected[index] = None
            for identity in identities:
                selected_by_identity[identity] = keep_index
        else:
            keep_index = len(selected)
            selected.append(item)
            for identity in identities:
                selected_by_identity[identity] = keep_index
    return [item for item in selected if isinstance(item, dict)]


def lerobot_root_from_episode(episode: dict[str, Any], fallback: str | Path | None = None) -> Path | None:
    video_path = Path(str(episode.get("primary_video_path") or episode.get("video_path") or ""))
    if str(video_path):
        for parent in video_path.parents:
            if (parent / "meta" / "info.json").exists():
                return parent
    if fallback:
        fallback_path = Path(fallback)
        if (fallback_path / "meta" / "info.json").exists():
            return fallback_path
    return None


def candidate_metadata_roots(episode: dict[str, Any], dataset_root: str | Path | None) -> list[Path]:
    roots = []
    video_path = Path(str(episode.get("primary_video_path") or episode.get("video_path") or ""))
    if str(video_path):
        for parent in video_path.parents:
            if (parent / "meta" / "common_record.json").exists() or (parent / "common_record.json").exists():
                roots.append(parent)
    lerobot_root = lerobot_root_from_episode(episode, dataset_root)
    if lerobot_root:
        roots.append(lerobot_root)
        roots.append(lerobot_root.parent)
    if dataset_root:
        roots.append(Path(dataset_root))
    unique = []
    for root in roots:
        if root and root not in unique:
            unique.append(root)
    return unique


def read_common_record(episode: dict[str, Any], dataset_root: str | Path | None) -> dict[str, Any]:
    for root in candidate_metadata_roots(episode, dataset_root):
        for path in (root / "common_record.json", root / "meta" / "common_record.json"):
            data = read_json_file(path)
            if data:
                return data
    return {}


def first_annotation(annotations: dict[str, Any], ordered_keys: list[str]) -> dict[str, Any]:
    for key in ordered_keys:
        annotation = annotations.get(key)
        if isinstance(annotation, dict):
            return annotation
    return {}


def ordered_annotation_keys(
    annotations: dict[str, Any],
    episode_order: list[str] | None = None,
) -> list[str]:
    keys = [str(key) for key in annotations]
    if not episode_order:
        return keys
    ordered = [key for key in episode_order if key in annotations]
    ordered.extend(key for key in keys if key not in ordered)
    return ordered


def standard_cameras(episode: dict[str, Any], primary_video_path: str) -> list[dict[str, Any]]:
    views = episode.get("views") if isinstance(episode.get("views"), dict) else {}
    result = []
    for camera, path in views.items():
        result.append({
            "id": len(result),
            "name": str(camera),
            "role": "primary" if str(path) == str(primary_video_path) else "secondary",
        })
    return result


def standard_scene(scene: dict[str, Any] | None) -> dict[str, Any]:
    scene = scene if isinstance(scene, dict) else {}
    location = scene.get("scene_location") if isinstance(scene.get("scene_location"), dict) else {}
    objects = []
    for obj in scene.get("objects") or []:
        if not isinstance(obj, dict):
            continue
        name = str(obj.get("name", "")).strip()
        if not name:
            continue
        item = {
            "id": len(objects),
            "name": name,
            "affordance": list(obj.get("affordance") or []),
        }
        color = str(obj.get("color", "")).strip()
        material = str(obj.get("material", "")).strip()
        if color:
            item["color"] = color
        if material:
            item["material"] = material
        objects.append(item)
    return {
        "scene_type": str(location.get("space") or scene.get("task_type", "")),
        "objects": objects,
    }


def standard_robot_setup(robot_setup: dict[str, Any] | None) -> dict[str, Any]:
    robot_setup = robot_setup if isinstance(robot_setup, dict) else {}
    embodiment = str(robot_setup.get("embodiment", "dual_arm"))
    base_mobility = str(robot_setup.get("base_mobility_type", "unknown") or "unknown")
    manipulators = []
    if embodiment == "single_arm":
        manipulators.append({
            "id": 0,
            "mount_position": "center",
            "end_effector_type": str(robot_setup.get("single_effector_type", "two_finger")),
        })
    else:
        manipulators.extend([
            {
                "id": 0,
                "mount_position": "left",
                "end_effector_type": str(robot_setup.get("left_effector_type", "two_finger")),
            },
            {
                "id": 1,
                "mount_position": "right",
                "end_effector_type": str(robot_setup.get("right_effector_type", "two_finger")),
            },
        ])
    return {
        "base": {
            "mobility_type": base_mobility,
        },
        "manipulators": manipulators,
    }


def standard_phase_list(phases, target_action: str, base_phases=None) -> list[dict[str, Any]]:
    result = []
    base_phases = [
        phase for phase in (base_phases or [])
        if isinstance(phase, dict)
    ]
    for phase in phases or []:
        if not isinstance(phase, dict):
            continue
        if str(phase.get("target_action", "primary") or "primary") != target_action:
            continue
        base = copy.deepcopy(base_phases[len(result)]) if len(result) < len(base_phases) else {}
        item = {
            "id": len(result),
            "start_frame": int(phase.get("start_frame", 0)),
            "end_frame": int(phase.get("end_frame", 0)),
            "action": str(phase.get("action", "")),
            "object": copy.deepcopy(phase.get("object", "")),
        }
        prediction_meta = phase.get("phases_prediction_meta") or phase.get("prediction_meta")
        if isinstance(prediction_meta, dict):
            item["phases_prediction_meta"] = prediction_meta
        base.update(item)
        item = base
        result.append(item)
    return result


def standard_action(action: dict[str, Any], phases, target_action: str, base_action=None) -> dict[str, Any]:
    result = copy.deepcopy(base_action) if isinstance(base_action, dict) else {}
    result.update({
        "subject": str(action.get("subject", "")),
        "skill": str(action.get("skill", "")),
        "text": str(action.get("text", "")),
        "slots": dict(action.get("slots") or {}),
        "phases": standard_phase_list(phases, target_action, result.get("phases")),
    })
    return result


def standard_action_from_base(base_action, phases, target_action: str) -> dict[str, Any] | None:
    if not isinstance(base_action, dict):
        return None
    result = copy.deepcopy(base_action)
    result["phases"] = standard_phase_list(phases, target_action, result.get("phases"))
    return result


def skill_action_snapshot(action: dict[str, Any], role: str = "primary") -> dict[str, Any]:
    return {
        "role": role,
        "subject": str(action.get("subject", "")),
        "skill": str(action.get("skill", "")),
        "text": str(action.get("text", "")),
        "slots": copy.deepcopy(action.get("slots") or {}),
    }


def subtask_skill_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        role = "primary" if index == 0 else "auxiliary"
        result.append(skill_action_snapshot(action, role))
    return result


def skill_identity_key(actions: list[dict[str, Any]]) -> str:
    return json.dumps(actions, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def skill_type_from_actions(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return ""
    first_skill = str(actions[0].get("skill", ""))
    if len(actions) == 1:
        return first_skill
    return "+".join(str(action.get("skill", "")) for action in actions)


def build_standard_skill_registry(annotations: dict[str, Any], ordered_keys: list[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    skills: list[dict[str, Any]] = []
    key_to_id: dict[str, int] = {}
    for key in ordered_keys:
        annotation = annotations.get(key)
        if not isinstance(annotation, dict):
            continue
        for subtask in annotation.get("subtasks") or []:
            if not isinstance(subtask, dict):
                continue
            actions = [
                action for action in (subtask.get("actions") or [])
                if isinstance(action, dict)
            ]
            skill_actions = subtask_skill_actions(actions)
            if not skill_actions:
                continue
            identity = skill_identity_key(skill_actions)
            if identity in key_to_id:
                continue
            skill_id = len(skills)
            key_to_id[identity] = skill_id
            text = subtask_description(actions)
            skills.append({
                "id": skill_id,
                "skill_type": skill_type_from_actions(skill_actions),
                "name": skill_type_from_actions(skill_actions),
                "text": text,
                "actions": skill_actions,
                "source": str((subtask.get("annotation_meta") or {}).get("source") or "human"),
                "created_by": "tool",
                "is_custom": any(action.get("skill") == "custom" for action in skill_actions),
            })
    return skills, key_to_id


def apply_standard_skill_refs(episode_item: dict[str, Any], skill_key_to_id: dict[str, int]) -> None:
    for subtask in episode_item.get("subtasks") or []:
        if not isinstance(subtask, dict):
            continue
        actions = []
        for action_key, role in (("primary_action", "primary"), ("auxiliary_action", "auxiliary")):
            action = subtask.get(action_key)
            if isinstance(action, dict):
                actions.append(skill_action_snapshot(action, role))
        identity = skill_identity_key(actions)
        if identity not in skill_key_to_id:
            continue
        subtask["skill_id"] = skill_key_to_id[identity]
        subtask["skill_match"] = {
            "method": "exact_actions",
            "confidence": 1.0,
            "review_required": False,
        }


def subtask_description(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return ""
    primary_text = str(actions[0].get("text", ""))
    if len(actions) == 1:
        return primary_text
    auxiliary_text = str(actions[1].get("text", ""))
    return f"{primary_text}, while {auxiliary_text} to assist/support the primary action"


def standard_subtask(subtask: dict[str, Any]) -> dict[str, Any]:
    actions = [
        action for action in (subtask.get("actions") or [])
        if isinstance(action, dict)
    ]
    phases = subtask.get("phases") or []
    result = copy.deepcopy(subtask.get("_standard_subtask_entry")) if isinstance(subtask.get("_standard_subtask_entry"), dict) else {}
    result.update({
        "id": 0,
        "start_frame": int(subtask.get("start_frame", 0)),
        "end_frame": int(subtask.get("end_frame", 0)),
        "state": str(subtask.get("state", "normal") or "normal"),
        "coordination_mode": str(subtask.get("coordination_mode", "")),
        "description": subtask_description(actions),
        "primary_action": (
            standard_action(actions[0], phases, "primary", result.get("primary_action"))
            if actions
            else standard_action_from_base(result.get("primary_action"), phases, "primary")
        ),
    })
    prediction_meta = subtask.get("subtask_prediction_meta") or subtask.get("prediction_meta")
    if isinstance(prediction_meta, dict):
        result["subtask_prediction_meta"] = prediction_meta
    if len(actions) > 1:
        result["auxiliary_action"] = standard_action(actions[1], phases, "auxiliary", result.get("auxiliary_action"))
    elif "auxiliary_action" in result:
        result.pop("auxiliary_action")
    return result


def standard_episode_annotation(
    annotation: dict[str, Any],
    episode_id: int,
    primary_video_path: str | Path | None = None,
) -> dict[str, Any]:
    episode = annotation.get("episode") or {}
    video_path = str(primary_video_path or episode.get("primary_video_path") or episode.get("video_path") or "")
    subtasks = []
    for subtask in annotation.get("subtasks") or []:
        if not isinstance(subtask, dict):
            continue
        item = standard_subtask(subtask)
        item["id"] = len(subtasks)
        subtasks.append(item)
    annotation_meta = annotation.get("annotation_meta")
    if not isinstance(annotation_meta, dict):
        annotation_meta = {"source": "human"}
    result = copy.deepcopy(annotation.get("_standard_episode_entry")) if isinstance(annotation.get("_standard_episode_entry"), dict) else {}
    result.update({
        "id": episode_id,
        "episode_video_path": video_path,
        "frame_count": int(episode.get("frames", 0)),
        "annotation_meta": annotation_meta,
        "subtasks": subtasks,
    })
    return result


def renumber_standard_episode(item: dict[str, Any], episode_id: int) -> dict[str, Any]:
    result = copy.deepcopy(item)
    result["id"] = episode_id
    for subtask_index, subtask in enumerate(result.get("subtasks") or []):
        if not isinstance(subtask, dict):
            continue
        subtask["id"] = subtask_index
        for action_key in ("primary_action", "auxiliary_action"):
            action = subtask.get(action_key)
            if not isinstance(action, dict):
                continue
            for phase_index, phase in enumerate(action.get("phases") or []):
                if isinstance(phase, dict):
                    phase["id"] = phase_index
    return result


def to_standard_task_annotation(
    bundle: dict[str, Any],
    dataset_type=DatasetType.UNKNOWN,
    dataset_root: str | Path | None = None,
    primary_video_paths: dict[str, str | Path] | None = None,
    episode_order: list[str] | None = None,
    existing_standard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    annotations = bundle.get("annotations") if isinstance(bundle.get("annotations"), dict) else {}
    ordered_keys = ordered_annotation_keys(annotations, episode_order)
    standard_skills, skill_key_to_id = build_standard_skill_registry(annotations, ordered_keys)
    representative = first_annotation(annotations, ordered_keys)
    representative_episode = representative.get("episode") or {}
    common_record = read_common_record(representative_episode, dataset_root)
    fallback_task_name, fallback_task_id = split_task_from_dataset_name(
        str(representative_episode.get("dataset_name", ""))
    )
    task = bundle.get("task") if isinstance(bundle.get("task"), dict) else {}
    shared_scene = task.get("scene") or representative.get("scene") or {}
    shared_robot_setup = task.get("robot_setup") or representative.get("robot_setup") or {}
    task_description = str(task.get("video_text") or representative.get("video_text") or "")
    primary_video_paths = primary_video_paths or {}
    first_key = ordered_keys[0] if ordered_keys else ""
    first_primary_path = str(
        primary_video_paths.get(first_key)
        or representative_episode.get("primary_video_path")
        or representative_episode.get("video_path")
        or ""
    )
    replacement_episodes = []
    for key in ordered_keys:
        annotation = annotations.get(key)
        if not isinstance(annotation, dict):
            continue
        if not annotation.get("subtasks"):
            continue
        episode_item = standard_episode_annotation(
            annotation,
            len(replacement_episodes),
            primary_video_paths.get(key),
        )
        apply_standard_skill_refs(episode_item, skill_key_to_id)
        match_identities = annotation_episode_identities(annotation, primary_video_paths.get(key), key)
        match_paths = {
            str(path)
            for path in (
                episode_item.get("episode_video_path"),
                (annotation.get("_standard_episode_entry") or {}).get("episode_video_path"),
            )
            if path
        }
        replacement_episodes.append((episode_item, match_paths, match_identities))
    episode_annotations = []
    used_replacements = set()
    if isinstance(existing_standard, dict):
        existing_paths = {
            str(item.get("episode_video_path", ""))
            for item in existing_standard.get("episode_annotation") or []
            if isinstance(item, dict)
        }
        existing_identities = set()
        for item in existing_standard.get("episode_annotation") or []:
            if isinstance(item, dict):
                existing_identities.update(standard_episode_identities(item))
        for replacement_index, (episode_item, match_paths, match_identities) in enumerate(replacement_episodes):
            if not match_paths.intersection(existing_paths) and not match_identities.intersection(existing_identities):
                episode_annotations.append(renumber_standard_episode(episode_item, len(episode_annotations)))
                used_replacements.add(replacement_index)
        for item in existing_standard.get("episode_annotation") or []:
            if not isinstance(item, dict):
                continue
            episode_path = str(item.get("episode_video_path", ""))
            if not episode_path or not item.get("subtasks"):
                continue
            item_identities = standard_episode_identities(item)
            replacement_index = next(
                (
                    index
                    for index, (_, match_paths, match_identities) in enumerate(replacement_episodes)
                    if (
                        index not in used_replacements
                        and (episode_path in match_paths or item_identities.intersection(match_identities))
                    )
                ),
                None,
            )
            if replacement_index is not None:
                replacement_item = replacement_episodes[replacement_index][0]
                episode_annotations.append(renumber_standard_episode(replacement_item, len(episode_annotations)))
                used_replacements.add(replacement_index)
            else:
                episode_annotations.append(renumber_standard_episode(item, len(episode_annotations)))
        for replacement_index, (episode_item, _, _) in enumerate(replacement_episodes):
            if replacement_index not in used_replacements:
                episode_annotations.append(renumber_standard_episode(episode_item, len(episode_annotations)))
    else:
        for episode_item, _, _ in replacement_episodes:
            episode_annotations.append(renumber_standard_episode(episode_item, len(episode_annotations)))
    episode_annotations = [
        renumber_standard_episode(item, index)
        for index, item in enumerate(dedupe_standard_episode_items(episode_annotations))
    ]
    task_id = str(common_record.get("task_id") or fallback_task_id or representative_episode.get("task_id", ""))
    result = copy.deepcopy(existing_standard) if isinstance(existing_standard, dict) else {}
    result.update({
        "version": STANDARD_VERSION,
        "annotation_spec_version": ANNOTATION_SPEC_VERSION,
        "task_id": task_id,
        "task_name": str(common_record.get("task_name") or fallback_task_name or representative_episode.get("task_id", "")),
        "task_type": str(shared_scene.get("task_type", "")),
        "data_type": normalized_data_type(dataset_type),
        "data_path": str(dataset_root or first_primary_path),
        "cameras": standard_cameras(representative_episode, first_primary_path),
        "task_description": task_description,
        "robot_setup": standard_robot_setup(shared_robot_setup),
        "scene": standard_scene(shared_scene),
        "skills": standard_skills,
        "episode_annotation": episode_annotations,
    })
    return result


def to_standard_annotation(
    annotation: dict[str, Any],
    dataset_type=DatasetType.UNKNOWN,
    data_path: str | Path | None = None,
    dataset_root: str | Path | None = None,
) -> dict[str, Any]:
    bundle = {
        "task": {
            "video_text": annotation.get("video_text", ""),
            "scene": annotation.get("scene"),
            "robot_setup": annotation.get("robot_setup"),
        },
        "annotations": {"episode_0": annotation},
    }
    return to_standard_task_annotation(
        bundle,
        dataset_type=dataset_type,
        dataset_root=dataset_root,
        primary_video_paths={"episode_0": data_path} if data_path else None,
        episode_order=["episode_0"],
    )


def standard_episode_paths(standard: dict[str, Any]) -> set[str]:
    paths = set()
    for episode in standard.get("episode_annotation") or []:
        if isinstance(episode, dict):
            path = str(episode.get("episode_video_path", "")).strip()
            if path:
                paths.add(path)
    return paths


def standard_episode_is_annotated(episode_entry: dict[str, Any] | None) -> bool:
    if not isinstance(episode_entry, dict):
        return False
    return any(isinstance(subtask, dict) for subtask in (episode_entry.get("subtasks") or []))


def annotation_source_label(source: str | None) -> str:
    value = str(source or "").strip().lower()
    labels = {
        "human": "人工(human)",
        "vlm": "VLM(vlm)",
        "automatic": "自动(automatic)",
        "hybrid": "混合(hybrid)",
    }
    return labels.get(value, value) if value else ""


def episode_annotation_source_text(episode_entry: dict[str, Any] | None) -> str:
    if not standard_episode_is_annotated(episode_entry):
        return ""
    meta = episode_entry.get("annotation_meta") if isinstance(episode_entry, dict) else {}
    if isinstance(meta, dict):
        label = annotation_source_label(meta.get("source"))
        if label:
            return label
    return annotation_source_label("human")


def mark_annotation_human_reviewed(annotation: dict[str, Any]) -> None:
    annotation_meta = annotation.get("annotation_meta")
    if not isinstance(annotation_meta, dict):
        annotation["annotation_meta"] = {"source": "human"}
        return
    source = str(annotation_meta.get("source", "")).strip().lower()
    if source in {"automatic", "vlm"}:
        annotation_meta["source"] = "hybrid"


def find_standard_episode(
    standard: dict[str, Any],
    episode: EpisodeItem,
    primary_video_path: str | Path | None = None,
) -> dict[str, Any] | None:
    candidate_paths = {str(path) for path in episode.camera_videos.values()}
    if primary_video_path:
        candidate_paths.add(str(primary_video_path))
    candidate_identities = episode_identities_from_paths(candidate_paths)
    if "/" in str(episode.episode_id):
        candidate_identities.add(str(episode.episode_id))
    if "__" in str(episode.annotation_stem):
        dataset, episode_name = str(episode.annotation_stem).rsplit("__", 1)
        candidate_identities.add(f"{dataset}/{episode_name}")
    identity_matches = [
        item
        for item in standard.get("episode_annotation") or []
        if isinstance(item, dict) and standard_episode_identities(item).intersection(candidate_identities)
    ]
    if identity_matches:
        return identity_matches[-1]
    for item in standard.get("episode_annotation") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("episode_video_path", "")) in candidate_paths:
            return item
    candidate_names = {Path(path).name for path in candidate_paths if path}
    candidate_stems = {
        Path(path).stem
        for path in candidate_paths
        if path
    }
    candidate_stems.update(
        value
        for value in (
            str(episode.episode_id).split("/")[-1],
            str(episode.annotation_stem).split("__")[-1],
        )
        if value
    )
    dataset_root_names = {
        value
        for value in (
            episode.dataset_root.name,
            str(episode.episode_id).split("/")[0],
            str(episode.annotation_stem).split("__")[0],
        )
        if value
    }
    path_matches = []
    for item in standard.get("episode_annotation") or []:
        if not isinstance(item, dict):
            continue
        episode_path = str(item.get("episode_video_path", "")).strip()
        if not episode_path:
            continue
        path = Path(episode_path)
        if path.name not in candidate_names and path.stem not in candidate_stems:
            continue
        if any(name in path.parts for name in dataset_root_names):
            path_matches.append(item)
    if len(path_matches) == 1:
        return path_matches[0]
    if episode.dataset_type == DatasetType.COROBOT:
        return None
    fallback_matches = []
    for item in standard.get("episode_annotation") or []:
        if not isinstance(item, dict):
            continue
        episode_path = str(item.get("episode_video_path", "")).strip()
        if not episode_path:
            continue
        path = Path(episode_path)
        if path.name in candidate_names or path.stem in candidate_stems:
            fallback_matches.append(item)
    if len(fallback_matches) == 1:
        return fallback_matches[0]
    return None


def action_from_standard(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    return {
        "subject": str(item.get("subject", "")),
        "skill": str(item.get("skill", "")),
        "text": str(item.get("text", "")),
        "slots": dict(item.get("slots") or {}),
    }


def phases_from_standard(action: dict[str, Any] | None, target_action: str) -> list[dict[str, Any]]:
    if not isinstance(action, dict):
        return []
    phases = []
    for phase in action.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        item = {
            "target_action": target_action,
            "start_frame": int(phase.get("start_frame", 0)),
            "end_frame": int(phase.get("end_frame", 0)),
            "action": str(phase.get("action", "")),
            "object": copy.deepcopy(phase.get("object", "")),
        }
        prediction_meta = phase.get("phases_prediction_meta") or phase.get("prediction_meta")
        if isinstance(prediction_meta, dict):
            item["prediction_meta"] = prediction_meta
        phases.append(item)
    return phases


def scene_from_standard(standard: dict[str, Any]) -> dict[str, Any] | None:
    scene = standard.get("scene")
    if not isinstance(scene, dict):
        return None
    return {
        "task_type": str(standard.get("task_type", "")),
        "scene_location": {"space": str(scene.get("scene_type", ""))},
        "objects": [
            {
                "name": str(obj.get("name", "")),
                "color": str(obj.get("color", "")).strip(),
                "material": str(obj.get("material", "")).strip(),
                "affordance": list(obj.get("affordance") or []),
            }
            for obj in scene.get("objects") or []
            if isinstance(obj, dict) and str(obj.get("name", "")).strip()
        ],
    }


def robot_setup_from_standard(standard: dict[str, Any]) -> dict[str, Any]:
    setup = standard.get("robot_setup") if isinstance(standard.get("robot_setup"), dict) else {}
    manipulators = setup.get("manipulators") if isinstance(setup.get("manipulators"), list) else []
    result = {
        "embodiment": "single_arm" if len(manipulators) == 1 else "dual_arm",
        "base_mobility_type": str((setup.get("base") or {}).get("mobility_type", "unknown")),
    }
    for manipulator in manipulators:
        if not isinstance(manipulator, dict):
            continue
        mount = str(manipulator.get("mount_position", ""))
        effector = str(manipulator.get("end_effector_type", "two_finger"))
        if mount == "left":
            result["left_effector_type"] = effector
        elif mount == "right":
            result["right_effector_type"] = effector
        elif mount == "center":
            result["single_effector_type"] = effector
    return result


def annotation_from_standard_episode(
    standard: dict[str, Any],
    episode_entry: dict[str, Any],
    episode_metadata: dict[str, Any],
) -> dict[str, Any]:
    annotation = create_empty_annotation(
        episode_metadata.get("primary_video_path") or episode_metadata.get("video_path") or "",
        int(episode_entry.get("frame_count") or episode_metadata.get("frames") or 0),
    )
    annotation["episode"].update(episode_metadata)
    annotation["episode"]["frames"] = int(episode_entry.get("frame_count") or episode_metadata.get("frames") or 0)
    annotation["video_text"] = str(standard.get("task_description", ""))
    annotation["scene"] = scene_from_standard(standard)
    annotation["robot_setup"] = robot_setup_from_standard(standard)
    annotation["annotation_meta"] = dict(episode_entry.get("annotation_meta") or {})
    annotation["_standard_episode_entry"] = copy.deepcopy(episode_entry)
    subtasks = []
    for subtask in episode_entry.get("subtasks") or []:
        if not isinstance(subtask, dict):
            continue
        primary = action_from_standard(subtask.get("primary_action"))
        auxiliary = action_from_standard(subtask.get("auxiliary_action"))
        actions = [action for action in (primary, auxiliary) if action]
        item = {
            "start_frame": int(subtask.get("start_frame", 0)),
            "end_frame": int(subtask.get("end_frame", 0)),
            "state": str(subtask.get("state", "normal") or "normal"),
            "coordination_mode": str(subtask.get("coordination_mode", "")),
            "text": render_subtask_text(actions),
            "actions": actions,
            "phases": (
                phases_from_standard(subtask.get("primary_action"), "primary")
                + phases_from_standard(subtask.get("auxiliary_action"), "auxiliary")
            ),
            "_standard_subtask_entry": copy.deepcopy(subtask),
        }
        prediction_meta = subtask.get("subtask_prediction_meta") or subtask.get("prediction_meta")
        if isinstance(prediction_meta, dict):
            item["prediction_meta"] = prediction_meta
        subtasks.append(item)
    annotation["subtasks"] = subtasks
    return annotation
