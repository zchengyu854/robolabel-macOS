from __future__ import annotations

import os

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

APP_NAME = "robolabletools"


def ui_scale(app: QApplication | None = None) -> float:
    raw_scale = os.environ.get("ROBOLABEL_UI_SCALE")
    if raw_scale:
        try:
            return max(0.8, min(float(raw_scale), 2.4))
        except ValueError:
            pass

    app = app or QApplication.instance()
    screen = app.primaryScreen() if app else None
    if not screen:
        return 1.0

    size = screen.availableGeometry().size()
    dpi_scale = screen.logicalDotsPerInch() / 96.0
    resolution_scale = min(size.width() / 2560.0, size.height() / 1440.0)
    return max(1.0, min(max(dpi_scale, resolution_scale), 1.6))


def scaled(value: int | float, app: QApplication | None = None) -> int:
    return max(1, int(round(value * ui_scale(app))))


APP_STYLESHEET_TEMPLATE = """
QWidget {
    background: #f4f6f7;
    color: #1f2933;
    font-size: {font_size}px;
}

QMainWindow {
    background: #eef2f3;
}

QLabel {
    color: #26323a;
}

QPushButton {
    background: #256f6f;
    color: #ffffff;
    border: 1px solid #1c5c5c;
    border-radius: {radius}px;
    padding: {button_padding_y}px {button_padding_x}px;
    min-height: {button_min_height}px;
}

QPushButton:hover {
    background: #2d8181;
}

QPushButton:pressed {
    background: #1c5c5c;
}

QPushButton:disabled {
    background: #cbd5da;
    color: #6b7780;
    border-color: #b8c4ca;
}

QLineEdit,
QTextEdit,
QComboBox,
QSpinBox,
QListWidget,
QTableWidget {
    background: #ffffff;
    color: #1f2933;
    border: 1px solid #c6d0d5;
    border-radius: 5px;
    selection-background-color: #d7ece9;
    selection-color: #102a2a;
}

QLineEdit,
QComboBox,
QSpinBox {
    min-height: 26px;
    padding: {input_padding_y}px {input_padding_x}px;
}

QSpinBox {
    padding-right: {spin_padding_right}px;
}

QSpinBox::up-button,
QSpinBox::down-button {
    subcontrol-origin: border;
    width: {spin_button_width}px;
    background: #e1ecec;
    border-left: 1px solid #9bb0b8;
}

QSpinBox::up-button {
    subcontrol-position: top right;
    border-top-right-radius: {input_radius}px;
    border-bottom: 1px solid #9bb0b8;
}

QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: {input_radius}px;
}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover {
    background: #cde4e1;
}

QSpinBox::up-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: {arrow_half}px solid transparent;
    border-right: {arrow_half}px solid transparent;
    border-bottom: {arrow_height}px solid #1c5c5c;
}

QSpinBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: {arrow_half}px solid transparent;
    border-right: {arrow_half}px solid transparent;
    border-top: {arrow_height}px solid #1c5c5c;
}

QTextEdit,
QListWidget,
QTableWidget {
    padding: {panel_padding}px;
}

QHeaderView::section {
    background: #dfe7ea;
    color: #22313a;
    border: 0;
    border-right: 1px solid #c6d0d5;
    border-bottom: 1px solid #c6d0d5;
    padding: {button_padding_y}px;
}

QGroupBox {
    border: 1px solid #c6d0d5;
    border-radius: {radius}px;
    margin-top: {group_margin_top}px;
    padding-top: {group_padding_top}px;
    background: #f9fbfb;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: {group_title_left}px;
    padding: 0 {panel_padding}px;
    color: #1c5c5c;
}

QSlider::groove:horizontal {
    background: #c6d0d5;
    height: {slider_groove_height}px;
    border-radius: {slider_groove_radius}px;
}

QSlider::handle:horizontal {
    background: #256f6f;
    width: {slider_handle_width}px;
    margin: -{slider_handle_margin}px 0;
    border-radius: {slider_handle_radius}px;
}

QScrollBar:vertical,
QScrollBar:horizontal {
    background: #edf1f2;
    border: 0;
}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {
    background: #aebdc4;
    border-radius: {panel_padding}px;
}
"""


def apply_app_theme(app) -> None:
    app.setApplicationName(APP_NAME)
    scale = ui_scale(app)
    font = QFont(app.font())
    font.setPointSizeF(max(10.0, 10.0 * scale))
    app.setFont(font)
    replacements = {
        "font_size": scaled(13, app),
        "radius": scaled(6, app),
        "input_radius": scaled(5, app),
        "button_padding_y": scaled(6, app),
        "button_padding_x": scaled(10, app),
        "button_min_height": scaled(24, app),
        "input_padding_y": scaled(2, app),
        "input_padding_x": scaled(6, app),
        "spin_padding_right": scaled(24, app),
        "spin_button_width": scaled(22, app),
        "arrow_half": scaled(5, app),
        "arrow_height": scaled(6, app),
        "panel_padding": scaled(4, app),
        "group_margin_top": scaled(8, app),
        "group_padding_top": scaled(10, app),
        "group_title_left": scaled(8, app),
        "slider_groove_height": scaled(6, app),
        "slider_groove_radius": scaled(3, app),
        "slider_handle_width": scaled(14, app),
        "slider_handle_margin": scaled(5, app),
        "slider_handle_radius": scaled(7, app),
    }
    stylesheet = APP_STYLESHEET_TEMPLATE
    for key, value in replacements.items():
        stylesheet = stylesheet.replace("{" + key + "}", str(value))
    app.setStyleSheet(stylesheet)
