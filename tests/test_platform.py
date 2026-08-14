import os
import sys

from lite_annotator.app import default_log_dir, ensure_macos_tool_path
from lite_annotator.video_decode import ffmpeg_install_hint


def test_default_log_dir_windows(monkeypatch):
    """Windows 下日志目录用 %LOCALAPPDATA%。"""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\dev\AppData\Local")
    log_dir = default_log_dir()
    assert log_dir.name == "robolabel"
    assert "AppData" in str(log_dir) and "Local" in str(log_dir)


def test_default_log_dir_windows_without_localappdata(monkeypatch):
    """Windows 无 %LOCALAPPDATA% 时回退用户主目录。"""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert default_log_dir().name == ".robolabel"


def test_default_log_dir_macos(monkeypatch):
    """macOS 保持原路径不变。"""
    monkeypatch.setattr(sys, "platform", "darwin")
    assert str(default_log_dir()).endswith("Library/Logs/robolabel")


def test_ensure_macos_tool_path_noop_on_windows(monkeypatch):
    """非 macOS 平台不修改 PATH。"""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("PATH", "C:\\Windows\\System32")
    ensure_macos_tool_path()
    assert os.environ["PATH"] == "C:\\Windows\\System32"


def test_ffmpeg_install_hint_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert ffmpeg_install_hint() == "winget install Gyan.FFmpeg"


def test_ffmpeg_install_hint_macos(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert ffmpeg_install_hint() == "brew install ffmpeg"