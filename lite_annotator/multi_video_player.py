from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lite_annotator.object_attributes import object_ref_text
from lite_annotator.ui_text import bilingual_label
from lite_annotator.ui_theme import scaled
from lite_annotator.video_decode import VideoFrameReader
from lite_annotator.vocabulary import option_label


class SubtaskTimelineBar(QWidget):
    COLORS = [
        "#2f7d7d",
        "#d47735",
        "#5d7fc0",
        "#7a62a8",
        "#4f8b4f",
        "#c0526d",
        "#7d6a2f",
        "#4d879c",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame_count = 0
        self.current_frame = 0
        self.subtasks: list[dict] = []
        self.setMinimumHeight(scaled(26))
        self.setMaximumHeight(scaled(34))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip(bilingual_label("subtask切分引导", "subtask segmentation guide"))

    def set_frame_count(self, frame_count: int) -> None:
        self.frame_count = max(int(frame_count or 0), 0)
        self.update()

    def set_current_frame(self, frame: int) -> None:
        self.current_frame = max(0, int(frame or 0))
        self.update()

    def set_subtasks(self, subtasks) -> None:
        self.subtasks = [
            item for item in (subtasks or [])
            if isinstance(item, dict)
        ]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(scaled(2), scaled(4), -scaled(2), -scaled(4))
        radius = scaled(5)

        painter.setPen(QPen(QColor("#b7c3c8"), 1))
        painter.setBrush(QColor("#e6ecee"))
        painter.drawRoundedRect(rect, radius, radius)

        if self.frame_count <= 0:
            self.draw_center_text(painter, rect, bilingual_label("未加载视频", "no video"))
            return

        sorted_subtasks = sorted(
            self.valid_subtasks(),
            key=lambda item: item[0],
        )
        last_end = -1
        for index, (start, end) in enumerate(sorted_subtasks, start=1):
            start = max(0, min(start, self.frame_count - 1))
            end = max(0, min(end, self.frame_count))
            if end < start:
                start, end = end, start
            if start < last_end:
                color = QColor("#c0392b")
            else:
                color = QColor(self.COLORS[(index - 1) % len(self.COLORS)])

            segment_rect = self.segment_rect(rect, start, end)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(segment_rect, scaled(3), scaled(3))
            if segment_rect.width() >= scaled(20):
                painter.setPen(QColor("#ffffff"))
                font = QFont(painter.font())
                font.setBold(True)
                font.setPointSizeF(max(7.0, font.pointSizeF() - 1))
                painter.setFont(font)
                painter.drawText(segment_rect, Qt.AlignCenter, str(index))
            last_end = max(last_end, end)

        self.draw_current_frame_marker(painter, rect)

    def valid_subtasks(self) -> list[tuple[int, int]]:
        ranges = []
        for subtask in self.subtasks:
            try:
                start = int(subtask.get("start_frame", 0))
                end = int(subtask.get("end_frame", start))
            except (TypeError, ValueError):
                continue
            ranges.append((start, end))
        return ranges

    def segment_rect(self, rect, start: int, end: int) -> QRectF:
        max_boundary = max(self.frame_count, 1)
        x1 = rect.left() + rect.width() * (start / max_boundary)
        x2 = rect.left() + rect.width() * (end / max_boundary)
        min_width = scaled(3)
        return QRectF(x1, rect.top(), max(x2 - x1, min_width), rect.height())

    def draw_current_frame_marker(self, painter, rect) -> None:
        max_frame = max(self.frame_count - 1, 1)
        frame = max(0, min(self.current_frame, self.frame_count - 1))
        x = rect.left() + rect.width() * (frame / max_frame)
        painter.setPen(QPen(QColor("#111827"), scaled(2)))
        painter.drawLine(int(x), rect.top() - scaled(3), int(x), rect.bottom() + scaled(3))

    def draw_center_text(self, painter, rect, text: str) -> None:
        painter.setPen(QColor("#66727a"))
        painter.drawText(rect, Qt.AlignCenter, text)


class MultiCameraVideoPlayer(QWidget):
    frame_changed = pyqtSignal(int)
    episode_loaded = pyqtSignal(int)
    MAIN_FRAME_SIZE = (640, 360)
    AUX_FRAME_SIZE = (320, 180)
    TITLE_HEIGHT = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self.readers_by_camera: dict[str, VideoFrameReader] = {}
        self.main_camera: str | None = None
        self.current_subtask: dict | None = None
        self.object_display_labels: dict[str, str] = {}
        self.action_display_labels: dict[str, str] = {}
        self.current_frame = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

        self.video_grid = QGridLayout()
        self.camera_labels: dict[str, QLabel] = {}
        self.camera_containers: dict[str, QWidget] = {}
        self.frame_label = QLabel(f"{bilingual_label('帧', 'frame')}: -/-")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self.seek)
        self.subtask_timeline = SubtaskTimelineBar(self)

        self.play_button = QPushButton(bilingual_label("播放", "play"))
        self.play_button.clicked.connect(self.toggle_playback)
        self.prev_button = QPushButton(bilingual_label("上一帧", "prev"))
        self.prev_button.clicked.connect(self.previous_frame)
        self.next_button = QPushButton(bilingual_label("下一帧", "next"))
        self.next_button.clicked.connect(self.next_frame)

        controls = QHBoxLayout()
        controls.addWidget(self.prev_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.frame_label)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.info_panel = QWidget()
        self.info_panel.setFixedWidth(self.scaled_main_frame_size()[0])
        self.info_panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.info_panel.setStyleSheet(
            "background-color: #f9fbfb; border: 1px solid #c6d0d5; border-radius: 6px;"
        )
        info_layout = QVBoxLayout(self.info_panel)
        info_layout.setContentsMargins(8, 6, 8, 6)
        info_layout.addWidget(self.info_label)

        self.video_column = QWidget()
        self.video_column.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        video_column_layout = QVBoxLayout(self.video_column)
        video_column_layout.setContentsMargins(0, 0, 0, 0)
        video_column_layout.addLayout(self.video_grid)
        video_column_layout.addWidget(self.slider)
        video_column_layout.addWidget(self.subtask_timeline)
        video_column_layout.addLayout(controls)
        video_column_layout.addWidget(self.info_panel)

        layout = QVBoxLayout(self)
        layout.addWidget(self.video_column, 0, Qt.AlignTop | Qt.AlignHCenter)
        self.set_placeholder()

    @property
    def frame_count(self) -> int:
        if not self.readers_by_camera:
            return 0
        return min(reader.frame_count for reader in self.readers_by_camera.values())

    def set_placeholder(self):
        self.clear_grid()
        label = QLabel(bilingual_label("未加载数据条目", "no episode loaded"))
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumSize(*self.scaled_main_frame_size())
        self.video_grid.addWidget(label, 0, 0)
        self.camera_labels = {"__placeholder__": label}
        self.set_current_subtask(None)

    def reset_episode(self):
        self.timer.stop()
        self.close_readers()
        self.readers_by_camera = {}
        self.main_camera = None
        self.current_frame = 0
        self.slider.blockSignals(True)
        self.slider.setRange(0, 0)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.frame_label.setText(f"{bilingual_label('帧', 'frame')}: -/-")
        self.subtask_timeline.set_frame_count(0)
        self.subtask_timeline.set_current_frame(0)
        self.subtask_timeline.set_subtasks([])
        self.play_button.setText(bilingual_label("播放", "play"))
        self.set_placeholder()

    def clear_grid(self):
        while self.video_grid.count():
            item = self.video_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def close_readers(self):
        for reader in self.readers_by_camera.values():
            reader.close()

    def load_episode(self, camera_videos: dict[str, Path], main_camera: str | None = None) -> None:
        if not camera_videos:
            raise RuntimeError("No camera videos selected")
        if len(camera_videos) > 3:
            raise RuntimeError("最多选择 3 个相机")

        self.close_readers()
        loaded: dict[str, VideoFrameReader] = {}
        for camera, video_path in camera_videos.items():
            loaded[camera] = VideoFrameReader(video_path)

        self.timer.stop()
        self.play_button.setText(bilingual_label("播放", "play"))
        self.readers_by_camera = loaded
        self.main_camera = main_camera if main_camera in loaded else next(iter(loaded))
        self.current_frame = 0
        self.rebuild_camera_grid()
        self.slider.blockSignals(True)
        self.slider.setRange(0, self.frame_count - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.subtask_timeline.set_frame_count(self.frame_count)
        self.subtask_timeline.set_current_frame(0)
        self.subtask_timeline.set_subtasks([])
        self.show_frame_after_layout()
        self.set_current_subtask(None)
        self.episode_loaded.emit(self.frame_count)

    def rebuild_camera_grid(self):
        self.clear_grid()
        self.camera_labels = {}
        self.camera_containers = {}
        self.info_panel.setFixedWidth(self.scaled_main_frame_size()[0])
        for column in range(2):
            self.video_grid.setColumnStretch(column, 0)
        for row in range(2):
            self.video_grid.setRowStretch(row, 0)
        for index, camera in enumerate(self.ordered_cameras()):
            is_main = index == 0
            frame_size = self.scaled_main_frame_size() if is_main else self.scaled_aux_frame_size()
            container = QWidget()
            container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            title = QLabel(camera)
            title.setAlignment(Qt.AlignCenter)
            title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            title.setFixedHeight(scaled(self.TITLE_HEIGHT))
            image = QLabel()
            image.setAlignment(Qt.AlignCenter)
            image.setFixedSize(*frame_size)
            image.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            image.setStyleSheet("background-color: #111;")
            layout.addWidget(title, 0)
            layout.addWidget(image, 0)
            if is_main:
                self.video_grid.addWidget(container, 0, 0, 1, 2, Qt.AlignHCenter | Qt.AlignTop)
            else:
                self.video_grid.addWidget(container, 1, index - 1, Qt.AlignHCenter | Qt.AlignTop)
            self.camera_labels[camera] = image
            self.camera_containers[camera] = container

    def scaled_main_frame_size(self) -> tuple[int, int]:
        return scaled(self.MAIN_FRAME_SIZE[0]), scaled(self.MAIN_FRAME_SIZE[1])

    def scaled_aux_frame_size(self) -> tuple[int, int]:
        return scaled(self.AUX_FRAME_SIZE[0]), scaled(self.AUX_FRAME_SIZE[1])

    def ordered_cameras(self) -> list[str]:
        cameras = list(self.readers_by_camera)
        if not cameras:
            return []
        main_camera = self.main_camera if self.main_camera in self.readers_by_camera else cameras[0]
        return [main_camera] + [camera for camera in cameras if camera != main_camera]

    def show_frame_after_layout(self) -> None:
        QTimer.singleShot(0, lambda: self.show_frame(self.current_frame))

    def set_current_subtask(self, subtask: dict | None) -> None:
        self.current_subtask = subtask
        self.refresh_current_subtask_label()

    def set_subtasks(self, subtasks) -> None:
        self.subtask_timeline.set_subtasks(subtasks)

    def set_display_label_maps(self, object_options=None, action_options=None) -> None:
        self.object_display_labels = dict(object_options or {})
        self.action_display_labels = dict(action_options or {})
        self.refresh_current_subtask_label()

    def display_value(self, value, labels):
        if isinstance(value, dict):
            value = object_ref_text(value)
        else:
            value = str(value or "")
        return option_label(value, labels.get(value, value)) if value else ""

    def refresh_current_subtask_label(self) -> None:
        subtask = self.current_subtask
        if not subtask:
            self.info_label.setText(bilingual_label("未选择subtask", "no subtask selected"))
            return
        start = int(subtask.get("start_frame", 0))
        end = int(subtask.get("end_frame", 0))
        text = subtask.get("text", "")
        lines = [
            "  |  ".join([
                bilingual_label("当前subtask", "current subtask"),
                f"{start}-{end}",
                text,
            ])
        ]
        phases = subtask.get("phases") or []
        if phases:
            lines.append("phase:")
            for index, phase in enumerate(phases, start=1):
                phase_start = int(phase.get("start_frame", 0))
                phase_end = int(phase.get("end_frame", 0))
                lines.append(
                    f"{index}. {phase_start}-{phase_end}  "
                    f"{self.display_value(phase.get('action', ''), self.action_display_labels)}  "
                    f"{self.display_value(phase.get('object', ''), self.object_display_labels)}"
                )
        self.info_label.setText("\n".join(lines))

    def show_frame(self, index: int) -> None:
        if not self.readers_by_camera:
            return
        index = max(0, min(index, self.frame_count - 1))
        self.current_frame = index
        for camera, reader in self.readers_by_camera.items():
            frame = reader.read(index)
            height, width, channels = frame.shape
            image = QImage(frame.data, width, height, channels * width, QImage.Format_RGB888)
            label = self.camera_labels[camera]
            pixmap = QPixmap.fromImage(image).scaled(
                label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            label.setPixmap(pixmap)
        self.frame_label.setText(f"{bilingual_label('帧', 'frame')}: {index}/{self.frame_count - 1}")
        self.subtask_timeline.set_current_frame(index)
        self.slider.blockSignals(True)
        self.slider.setValue(index)
        self.slider.blockSignals(False)
        self.frame_changed.emit(index)

    def seek(self, index: int) -> None:
        self.show_frame(index)

    def next_frame(self) -> None:
        if not self.readers_by_camera:
            return
        if self.current_frame >= self.frame_count - 1:
            self.timer.stop()
            self.play_button.setText(bilingual_label("播放", "play"))
            return
        self.show_frame(self.current_frame + 1)

    def previous_frame(self) -> None:
        self.show_frame(self.current_frame - 1)

    def toggle_playback(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.play_button.setText(bilingual_label("播放", "play"))
        else:
            self.timer.start(50)
            self.play_button.setText(bilingual_label("暂停", "pause"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.show_frame(self.current_frame)

    def closeEvent(self, event):
        self.close_readers()
        super().closeEvent(event)
