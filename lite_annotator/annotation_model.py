from __future__ import annotations

from pathlib import Path
from typing import Any

from common.skill_schema import (
    DEFAULT_ROBOT_SETUP,
    SCHEMA_VERSION,
    TEMPLATE_SET_VERSION,
    load_coordination_modes,
    load_scene_templates,
    load_skill_templates,
    normalize_legacy_annotation,
    validate_annotation,
)


def build_episode_info(video_path: str | Path, frame_count: int = 0) -> dict[str, Any]:
    path = Path(video_path)
    return {
        "episode_id": path.stem,
        "task_id": str(path),
        "dataset_name": "",
        "video_path": str(path),
        "primary_video_path": str(path),
        "views": {},
        "frames": int(frame_count),
    }


def create_empty_annotation(video_path: str | Path, frame_count: int = 0) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "template_set_version": TEMPLATE_SET_VERSION,
        "episode": build_episode_info(video_path, frame_count),
        "robot_setup": dict(DEFAULT_ROBOT_SETUP),
        "video_text": "",
        "scene": None,
        "subtasks": [],
    }


def normalize_annotation(annotation: dict[str, Any]) -> dict[str, Any]:
    _, skill_templates = load_skill_templates()
    normalized = normalize_legacy_annotation(annotation, skill_templates)
    normalized.setdefault("schema_version", SCHEMA_VERSION)
    normalized.setdefault("template_set_version", TEMPLATE_SET_VERSION)
    normalized.setdefault("robot_setup", dict(DEFAULT_ROBOT_SETUP))
    normalized.setdefault("video_text", "")
    normalized.setdefault("subtasks", [])
    return normalized


def validate_lite_annotation(annotation: dict[str, Any], frame_count: int = 0) -> list[str]:
    errors: list[str] = []
    if not str(annotation.get("video_text", "")).strip():
        errors.append("任务描述不能为空")
    if not annotation.get("scene"):
        errors.append("场景标注不能为空")

    subtasks = annotation.get("subtasks") or []
    if not subtasks:
        errors.append("至少需要一个片段")

    previous_end = None
    for idx, subtask in enumerate(subtasks):
        start_frame = int(subtask.get("start_frame", -1))
        end_frame = int(subtask.get("end_frame", -1))
        if start_frame < 0 or end_frame < 0:
            errors.append(f"片段{idx + 1}帧范围不能为空")
        if start_frame >= end_frame:
            errors.append(f"片段{idx + 1}开始帧必须小于结束帧")
        if frame_count and end_frame > frame_count:
            errors.append(f"片段{idx + 1}结束帧超出视频范围")
        expected_start = 0 if idx == 0 else previous_end
        if idx == 0 and start_frame != 0:
            errors.append("第1个subtask必须从第0帧开始")
        elif idx > 0 and start_frame != expected_start:
            errors.append(
                f"第{idx + 1}个subtask必须从上一段结束帧开始，"
                f"应为{expected_start}，实际为{start_frame}"
            )
        phases = subtask.get("phases") or []
        if phases:
            previous_phase_end = None
            for phase_idx, phase in enumerate(phases):
                phase_start = int(phase.get("start_frame", -1))
                phase_end = int(phase.get("end_frame", -1))
                expected_phase_start = start_frame if phase_idx == 0 else previous_phase_end
                if phase_start < start_frame or phase_end > end_frame:
                    errors.append(f"第{idx + 1}个subtask的第{phase_idx + 1}个phase必须在subtask帧范围内")
                if phase_start >= phase_end:
                    errors.append(f"第{idx + 1}个subtask的第{phase_idx + 1}个phase开始帧必须小于结束帧")
                if phase_idx == 0 and phase_start != start_frame:
                    errors.append(
                        f"第{idx + 1}个subtask的第1个phase必须从subtask起始帧{start_frame}开始，"
                        f"实际为{phase_start}"
                    )
                elif phase_idx > 0 and phase_start != expected_phase_start:
                    errors.append(
                        f"第{idx + 1}个subtask的第{phase_idx + 1}个phase必须从上一phase结束帧开始，"
                        f"应为{expected_phase_start}，实际为{phase_start}"
                    )
                previous_phase_end = phase_end
            if previous_phase_end != end_frame:
                errors.append(
                    f"第{idx + 1}个subtask的最后一个phase必须结束于subtask结束帧{end_frame}，"
                    f"实际为{previous_phase_end}"
                )
        previous_end = end_frame
    if subtasks and frame_count and previous_end != frame_count:
        errors.append(f"最后一个subtask必须结束于视频尾帧后一帧{frame_count}，实际为{previous_end}")

    try:
        _, skill_templates = load_skill_templates()
        coordination_modes = load_coordination_modes()
        scene_template = load_scene_templates()
        schema_error = validate_annotation(
            annotation,
            skill_templates,
            coordination_modes,
            scene_template,
        )
        if schema_error:
            errors.append(schema_error)
    except Exception as exc:
        errors.append(str(exc))
    return errors
