from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PyQt5.QtCore import QLibraryInfo, Qt
from PyQt5.QtWidgets import QApplication

from lite_annotator.main_window import MainWindow
from lite_annotator.ui_theme import apply_app_theme, scaled


def configure_qt_plugin_path() -> None:
    """设置Qt插件路径，PyInstaller打包后需要明确指定。"""
    if getattr(sys, "frozen", False):
        # 打包环境：从_MEIPASS读取插件
        bundle_dir = sys._MEIPASS
        plugin_path = os.path.join(bundle_dir, "PyQt5", "Qt5", "plugins")
        if not os.path.exists(plugin_path):
            plugin_path = os.path.join(bundle_dir, "PyQt5", "Qt", "plugins")
        if not os.path.exists(plugin_path):
            plugin_path = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    else:
        plugin_path = QLibraryInfo.location(QLibraryInfo.PluginsPath)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path


def ensure_macos_tool_path() -> None:
    """macOS GUI 启动的 app PATH 很短，补上 Homebrew 目录；其他平台无需处理。"""
    if sys.platform != "darwin":
        return
    current = os.environ.get("PATH", "")
    missing = [
        p
        for p in ("/opt/homebrew/bin", "/opt/homebrew/opt/ffmpeg/bin", "/usr/local/bin")
        if p not in current.split(":")
    ]
    if missing:
        os.environ["PATH"] = ":".join(missing + [current])


def default_log_dir() -> Path:
    """平台默认日志目录：macOS 用 ~/Library/Logs，Windows/Linux 用 %LOCALAPPDATA%（缺省回退 ~/.robolabel）。"""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "robolabel"
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "robolabel"
    return Path.home() / ".robolabel"


def setup_logging() -> None:
    """windowed 模式下无终端，日志落盘便于排障；目录不可写时静默降级。"""
    try:
        log_dir = default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=log_dir / "robolabel.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except OSError:
        return  # 日志不可写不应阻止应用启动

    def log_exception(exc_type, exc, tb):
        logging.error("Uncaught exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = log_exception


def main() -> int:
    ensure_macos_tool_path()
    setup_logging()
    configure_qt_plugin_path()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setLibraryPaths([QLibraryInfo.location(QLibraryInfo.PluginsPath)])
    apply_app_theme(app)
    window = MainWindow()
    window.resize(scaled(1400, app), scaled(850, app))
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
