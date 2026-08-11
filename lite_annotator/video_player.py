from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from lite_annotator.video_decode import VideoFrameReader


class VideoPlayer(QWidget):
    frame_changed = pyqtSignal(int)
    video_loaded = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.reader: VideoFrameReader | None = None
        self.current_frame = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

        self.image_label = QLabel("No video loaded")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 360)

        self.frame_label = QLabel("Frame: -/-")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self.seek)

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_playback)
        self.prev_button = QPushButton("Prev")
        self.prev_button.clicked.connect(self.previous_frame)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_frame)

        controls = QHBoxLayout()
        controls.addWidget(self.prev_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.frame_label)

        layout = QVBoxLayout(self)
        layout.addWidget(self.image_label)
        layout.addWidget(self.slider)
        layout.addLayout(controls)

    @property
    def frame_count(self) -> int:
        return self.reader.frame_count if self.reader else 0

    def load_video(self, path: str | Path) -> None:
        if self.reader:
            self.reader.close()
        reader = VideoFrameReader(path)

        self.timer.stop()
        self.play_button.setText("Play")
        self.reader = reader
        self.current_frame = 0
        self.slider.blockSignals(True)
        self.slider.setRange(0, self.frame_count - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.show_frame(0)
        self.video_loaded.emit(self.frame_count)

    def show_frame(self, index: int) -> None:
        if not self.reader:
            return
        index = max(0, min(index, self.frame_count - 1))
        self.current_frame = index
        frame = self.reader.read(index)
        height, width, channels = frame.shape
        image = QImage(frame.data, width, height, channels * width, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(pixmap)
        self.frame_label.setText(f"Frame: {index + 1}/{self.frame_count}")
        self.slider.blockSignals(True)
        self.slider.setValue(index)
        self.slider.blockSignals(False)
        self.frame_changed.emit(index)

    def seek(self, index: int) -> None:
        self.show_frame(index)

    def next_frame(self) -> None:
        if not self.reader:
            return
        if self.current_frame >= self.frame_count - 1:
            self.timer.stop()
            self.play_button.setText("Play")
            return
        self.show_frame(self.current_frame + 1)

    def previous_frame(self) -> None:
        self.show_frame(self.current_frame - 1)

    def toggle_playback(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.play_button.setText("Play")
        else:
            self.timer.start(50)
            self.play_button.setText("Pause")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.show_frame(self.current_frame)
