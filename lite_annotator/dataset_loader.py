from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DatasetType(str, Enum):
    LEROBOT = "lerobot2.1"
    COROBOT = "corobot"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EpisodeItem:
    episode_id: str
    display_name: str
    annotation_stem: str
    dataset_type: DatasetType
    dataset_root: Path
    camera_videos: dict[str, Path]
    primary_video_path: Path


def is_lerobot_dataset(root: str | Path) -> bool:
    root = Path(root)
    return (
        (root / "meta" / "info.json").exists()
        and any((root / "videos").glob("chunk-*/*/*.mp4"))
    )


def detect_dataset_type(root: str | Path) -> DatasetType:
    root = Path(root)
    if is_lerobot_dataset(root):
        return DatasetType.LEROBOT
    if any(is_lerobot_dataset(child) for child in root.iterdir() if child.is_dir()):
        return DatasetType.COROBOT
    return DatasetType.UNKNOWN


def lerobot_roots(root: str | Path) -> list[Path]:
    root = Path(root)
    dataset_type = detect_dataset_type(root)
    if dataset_type == DatasetType.LEROBOT:
        return [root]
    if dataset_type == DatasetType.COROBOT:
        return sorted(
            child
            for child in root.iterdir()
            if child.is_dir() and is_lerobot_dataset(child)
        )
    return []


def camera_dirs(dataset_root: Path) -> dict[str, list[Path]]:
    cameras: dict[str, list[Path]] = {}
    for path in sorted((dataset_root / "videos").glob("chunk-*/*")):
        if not path.is_dir():
            continue
        if any(path.glob("*.mp4")):
            cameras.setdefault(path.name, []).append(path)
    return cameras


def list_cameras(root: str | Path) -> list[str]:
    cameras = set()
    for dataset_root in lerobot_roots(root):
        cameras.update(camera_dirs(dataset_root))
    return sorted(cameras)


def videos_by_episode(dataset_root: Path, camera: str) -> dict[str, Path]:
    videos: dict[str, Path] = {}
    for cam_dir in camera_dirs(dataset_root).get(camera, []):
        for video_path in sorted(cam_dir.glob("*.mp4")):
            videos[video_path.stem] = video_path
    return videos


def list_episodes(root: str | Path, selected_cameras: list[str]) -> list[EpisodeItem]:
    root = Path(root)
    dataset_type = detect_dataset_type(root)
    if dataset_type == DatasetType.UNKNOWN:
        return []
    if not selected_cameras:
        return []
    if len(selected_cameras) > 3:
        raise ValueError("最多选择 3 个相机")

    episodes: list[EpisodeItem] = []
    for dataset_root in lerobot_roots(root):
        per_camera = {
            camera: videos_by_episode(dataset_root, camera)
            for camera in selected_cameras
        }
        common_episode_names = set.intersection(
            *[set(videos) for videos in per_camera.values()]
        ) if per_camera else set()
        for episode_name in sorted(common_episode_names):
            camera_videos = {
                camera: per_camera[camera][episode_name]
                for camera in selected_cameras
            }
            if dataset_type == DatasetType.COROBOT:
                episode_id = f"{dataset_root.name}/{episode_name}"
                annotation_stem = f"{dataset_root.name}__{episode_name}"
                display_name = episode_id
            else:
                episode_id = episode_name
                annotation_stem = episode_name
                display_name = episode_name
            primary_video_path = next(iter(camera_videos.values()))
            episodes.append(
                EpisodeItem(
                    episode_id=episode_id,
                    display_name=display_name,
                    annotation_stem=annotation_stem,
                    dataset_type=dataset_type,
                    dataset_root=dataset_root,
                    camera_videos=camera_videos,
                    primary_video_path=primary_video_path,
                )
            )
    return sorted(episodes, key=lambda item: item.display_name)
