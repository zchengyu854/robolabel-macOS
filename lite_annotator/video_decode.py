from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

import cv2
import numpy as np


def ffmpeg_install_hint() -> str:
    """按平台返回 ffmpeg 安装命令提示。"""
    if sys.platform == "darwin":
        return "brew install ffmpeg"
    if sys.platform == "win32":
        return "winget install Gyan.FFmpeg"
    return "sudo apt install ffmpeg"


class VideoFrameReader:
    def __init__(self, path: str | Path, cache_size: int = 48):
        self.path = Path(path)
        self.cache_size = max(int(cache_size), 1)
        self.cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self.capture = cv2.VideoCapture(str(self.path))
        self.width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        self.height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self.fps = float(self.capture.get(cv2.CAP_PROP_FPS) or 0.0)
        self.frame_count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if self.width <= 0 or self.height <= 0 or self.frame_count <= 0:
            info = probe_video_info(self.path)
            self.width = info["width"]
            self.height = info["height"]
            self.fps = info["fps"]
            self.frame_count = info["frame_count"]

        self.use_ffmpeg = False
        test_frame = self._read_with_opencv(0)
        if test_frame is None:
            self.use_ffmpeg = True
        else:
            self.cache[0] = test_frame

    def read(self, index: int) -> np.ndarray:
        if self.frame_count <= 0:
            raise RuntimeError(f"Could not decode video: {self.path}")
        index = max(0, min(int(index), self.frame_count - 1))
        if index in self.cache:
            frame = self.cache.pop(index)
            self.cache[index] = frame
            return frame

        frame = self._read_with_ffmpeg(index) if self.use_ffmpeg else self._read_with_opencv(index)
        if frame is None:
            frame = self._read_with_ffmpeg(index)
            self.use_ffmpeg = True
        if frame is None:
            raise RuntimeError(f"Could not decode video frame {index}: {self.path}")
        self.cache[index] = frame
        while len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return frame

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        self.cache.clear()

    def _read_with_opencv(self, index: int) -> np.ndarray | None:
        if self.capture is None:
            self.capture = cv2.VideoCapture(str(self.path))
        with muted_stderr():
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            success, frame = self.capture.read()
        if not success or frame is None:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def _read_with_ffmpeg(self, index: int) -> np.ndarray | None:
        if shutil.which("ffmpeg") is None:
            return None
        timestamp = 0.0 if self.fps <= 0 else index / self.fps
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.6f}",
            "-i",
            str(self.path),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ]
        result = subprocess.run(command, capture_output=True)
        frame_size = self.width * self.height * 3
        if result.returncode != 0 or len(result.stdout) != frame_size:
            return None
        return np.frombuffer(result.stdout, dtype=np.uint8).reshape(
            (self.height, self.width, 3)
        ).copy()


def read_video_rgb_frames(path: str | Path) -> list[np.ndarray]:
    video_path = Path(path)
    frames = read_video_with_opencv(video_path)
    if frames:
        return frames
    return read_video_with_ffmpeg(video_path)


def decode_video_frames(path: str | Path) -> list[np.ndarray]:
    return read_video_rgb_frames(path)


def read_video_with_opencv(path: Path) -> list[np.ndarray]:
    with muted_stderr():
        capture = cv2.VideoCapture(str(path))
        frames = []
        success, frame = capture.read()
        while success:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            success, frame = capture.read()
        capture.release()
        return frames


def read_video_with_ffmpeg(path: Path) -> list[np.ndarray]:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError(
            f"Could not decode video: {path}. OpenCV could not read this codec, "
            "and ffmpeg/ffprobe is not available.\n"
            f"无法解码该视频：缺少 ffmpeg，请先安装（{ffmpeg_install_hint()}）后重试。"
        )

    width, height = probe_video_size(path)
    frame_size = width * height * 3
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-vsync",
        "0",
        "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None

    frames = []
    while True:
        chunk = process.stdout.read(frame_size)
        if not chunk:
            break
        if len(chunk) != frame_size:
            process.kill()
            raise RuntimeError(f"Could not decode complete frame from video: {path}")
        frame = np.frombuffer(chunk, dtype=np.uint8).reshape((height, width, 3)).copy()
        frames.append(frame)

    _, stderr = process.communicate()
    if process.returncode != 0 or not frames:
        message = stderr.decode("utf-8", errors="replace").strip()
        detail = f" ffmpeg: {message}" if message else ""
        raise RuntimeError(f"Could not decode video: {path}.{detail}")
    return frames


def probe_video_size(path: Path) -> tuple[int, int]:
    info = probe_video_info(path)
    return info["width"], info["height"]


def probe_video_info(path: Path) -> dict[str, int | float]:
    command = [
        "ffprobe",
        "-hide_banner",
        "-loglevel",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,nb_frames,avg_frame_rate,r_frame_rate,duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    info = json.loads(result.stdout)
    stream = (info.get("streams") or [{}])[0]
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Could not probe video size: {path}")
    fps = parse_frame_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
    frame_count = int(stream.get("nb_frames") or 0)
    if frame_count <= 0:
        duration = float(stream.get("duration") or 0.0)
        frame_count = int(round(duration * fps)) if duration > 0 and fps > 0 else 0
    if frame_count <= 0:
        raise RuntimeError(f"Could not probe video frame count: {path}")
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
    }


def parse_frame_rate(value) -> float:
    text = str(value or "")
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        denominator_value = float(denominator or 0)
        return float(numerator or 0) / denominator_value if denominator_value else 0.0
    return float(text or 0.0)


@contextmanager
def muted_stderr():
    saved_stderr = os.dup(2)
    try:
        with open(os.devnull, "w") as devnull:
            os.dup2(devnull.fileno(), 2)
            yield
    finally:
        os.dup2(saved_stderr, 2)
        os.close(saved_stderr)
