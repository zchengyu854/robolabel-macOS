import os
import sys

from lite_annotator.paths import resource_path


def test_resource_path_source_layout():
    """源码运行时 resource_path 指向项目根下路径且资源存在。"""
    path = resource_path("config/lite_vocabulary.json")
    assert path.name == "lite_vocabulary.json"
    assert path.exists()


def test_resource_path_frozen():
    """冻结（打包）时 resource_path 基于 sys._MEIPASS。"""
    sys._MEIPASS = "/tmp/fake"
    try:
        assert str(resource_path("config/x")) == "/tmp/fake/config/x"
    finally:
        del sys._MEIPASS


def test_ensure_macos_tool_path(monkeypatch):
    """GUI 启动 PATH 注入 Homebrew 目录，且不重复追加。"""
    from lite_annotator.app import ensure_macos_tool_path

    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    ensure_macos_tool_path()
    assert "/opt/homebrew/bin" in os.environ["PATH"]

    first = os.environ["PATH"]
    ensure_macos_tool_path()
    assert os.environ["PATH"] == first
