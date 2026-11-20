"""
Review Video Player with Multi-Version Switcher.
Uses PySide6 QtMultimedia to play MP4/MOV review renders and compare versions seamlessly.
"""

from pathlib import Path
from typing import Dict
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton,
    QSlider, QStyle, QVBoxLayout
)


class ReviewPlayerDialog(QDialog):
    def __init__(self, shot_name: str, review_versions: Dict[str, str], initial_version: str, parent=None):
        super().__init__(parent)
        self.shot_name = shot_name
        self.review_versions = review_versions  # {"v001": "path/to/v001.mp4", ...}
        self.current_version = initial_version

        self.setWindowTitle(f"Review Player - {shot_name}")
        self.resize(900, 600)
        self.setMinimumSize(640, 480)

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)

        self.init_ui()
        self.setup_shortcuts()

        # Load initial video
        if initial_version in self.review_versions:
            self.load_video(self.review_versions[initial_version])

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Top Bar: Shot info + Version Switcher
        top_bar = QHBoxLayout()
        title_lbl = QLabel(f"<b>Shot:</b> <span style='color: #4da6ff;'>{self.shot_name}</span>")
        title_lbl.setStyleSheet("font-size: 14px;")
        top_bar.addWidget(title_lbl)

        top_bar.addStretch()

        top_bar.addWidget(QLabel("<b>Review Version:</b>"))
        self.ver_combo = QComboBox()
        for v in sorted(self.review_versions.keys(), reverse=True):
            self.ver_combo.addItem(v)

        idx = self.ver_combo.findText(self.current_version)
        if idx >= 0:
            self.ver_combo.setCurrentIndex(idx)

        self.ver_combo.currentTextChanged.connect(self.on_version_selected)
        top_bar.addWidget(self.ver_combo)

        layout.addLayout(top_bar)

        # Video Display
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 4px;")
        self.media_player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget, stretch=1)

        # Timeline Slider
        slider_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #a0a0a0; font-family: Consolas;")

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)

        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.time_label)
        layout.addLayout(slider_layout)

        # Controls Bar
        ctrl_layout = QHBoxLayout()

        self.btn_step_back = QPushButton("◀")
        self.btn_step_back.setToolTip("Step Back 1s (Left Arrow)")
        self.btn_step_back.clicked.connect(self.step_backward)
        ctrl_layout.addWidget(self.btn_step_back)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_play.clicked.connect(self.play_pause)
        ctrl_layout.addWidget(self.btn_play)

        self.btn_step_fwd = QPushButton("▶")
        self.btn_step_fwd.setToolTip("Step Forward 1s (Right Arrow)")
        self.btn_step_fwd.clicked.connect(self.step_forward)
        ctrl_layout.addWidget(self.btn_step_fwd)

        self.btn_loop = QPushButton("Loop: ON")
        self.is_looping = True
        self.btn_loop.clicked.connect(self.toggle_loop)
        ctrl_layout.addWidget(self.btn_loop)

        ctrl_layout.addStretch()

        self.path_label = QLabel("")
        self.path_label.setStyleSheet("color: #707070; font-size: 11px;")
        ctrl_layout.addWidget(self.path_label)

        layout.addLayout(ctrl_layout)

        # Player Signals
        self.media_player.positionChanged.connect(self.on_position_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)

    def setup_shortcuts(self):
        # Spacebar for Play/Pause
        shortcut_space = QShortcut(QKeySequence(Qt.Key_Space), self)
        shortcut_space.activated.connect(self.play_pause)

        # Left / Right arrows
        shortcut_left = QShortcut(QKeySequence(Qt.Key_Left), self)
        shortcut_left.activated.connect(self.step_backward)

        shortcut_right = QShortcut(QKeySequence(Qt.Key_Right), self)
        shortcut_right.activated.connect(self.step_forward)

    def load_video(self, video_path: str):
        path = Path(video_path)
        if path.exists():
            self.path_label.setText(path.name)
            self.media_player.setSource(QUrl.fromLocalFile(str(path)))
            self.media_player.play()
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

    def on_version_selected(self, version: str):
        if version in self.review_versions:
            self.current_version = version
            self.load_video(self.review_versions[version])

    def play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        else:
            self.media_player.play()
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

    def step_backward(self):
        pos = max(0, self.media_player.position() - 1000)
        self.media_player.setPosition(pos)

    def step_forward(self):
        dur = self.media_player.duration()
        pos = min(dur, self.media_player.position() + 1000)
        self.media_player.setPosition(pos)

    def toggle_loop(self):
        self.is_looping = not self.is_looping
        self.btn_loop.setText(f"Loop: {'ON' if self.is_looping else 'OFF'}")

    def on_position_changed(self, position: int):
        self.slider.setValue(position)
        self.update_time_label()

    def on_duration_changed(self, duration: int):
        self.slider.setRange(0, duration)
        self.update_time_label()

    def set_position(self, position: int):
        self.media_player.setPosition(position)

    def update_time_label(self):
        pos_sec = self.media_player.position() // 1000
        dur_sec = self.media_player.duration() // 1000
        pos_str = f"{pos_sec // 60:02d}:{pos_sec % 60:02d}"
        dur_str = f"{dur_sec // 60:02d}:{dur_sec % 60:02d}"
        self.time_label.setText(f"{pos_str} / {dur_str}")

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia and self.is_looping:
            self.media_player.setPosition(0)
            self.media_player.play()

    def closeEvent(self, event):
        self.media_player.stop()
        super().closeEvent(event)
