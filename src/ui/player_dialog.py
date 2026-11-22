"""
Review Video Player with Multi-Version Switcher.
Frame-accurate playback with step-by-frame navigation and TC/frame counter.
"""

from pathlib import Path
from typing import Dict, Optional
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton,
    QSlider, QStyle, QVBoxLayout
)
from .theme import get_app_icon


class ReviewPlayerDialog(QDialog):
    def __init__(
        self,
        shot_name: str,
        review_versions: Dict[str, str],
        initial_version: str,
        fps: float = 24.0,
        frame_start: int = 1001,
        parent=None
    ):
        super().__init__(parent)
        self.shot_name = shot_name
        self.review_versions = review_versions  # {"v001": "path/to/v001.mp4", ...}
        self.current_version = initial_version
        self.fps = float(fps) if fps > 0 else 24.0
        self.frame_start = int(frame_start)
        self.ms_per_frame = 1000.0 / self.fps

        self.setWindowTitle(f"Review Player - {shot_name} ({self.fps} fps)")
        self.setWindowIcon(get_app_icon())
        self.resize(920, 620)
        self.setMinimumSize(660, 500)

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

        # Top Bar: Shot info + Version Switcher + FPS Info
        top_bar = QHBoxLayout()
        title_lbl = QLabel(f"<b>Shot:</b> <span style='color: #4da6ff;'>{self.shot_name}</span> &nbsp;|&nbsp; <span style='color: #a0a0aa;'>{self.fps} fps</span>")
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

        # Timeline Slider + Frame Counter Display
        slider_layout = QHBoxLayout()
        self.frame_label = QLabel(f"Frame: {self.frame_start} / {self.frame_start}")
        self.frame_label.setStyleSheet("color: #4da6ff; font-family: Consolas, monospace; font-size: 13px; font-weight: bold; min-width: 180px;")

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.on_slider_scrubbed)

        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.frame_label)
        layout.addLayout(slider_layout)

        # Controls Bar
        ctrl_layout = QHBoxLayout()

        self.btn_step_back_10 = QPushButton("⏪ -10")
        self.btn_step_back_10.setToolTip("Step Back 10 Frames (Shift + Left Arrow)")
        self.btn_step_back_10.clicked.connect(lambda: self.step_frames(-10))
        ctrl_layout.addWidget(self.btn_step_back_10)

        self.btn_step_back = QPushButton("◀ -1")
        self.btn_step_back.setToolTip("Step Back 1 Frame (Left Arrow)")
        self.btn_step_back.clicked.connect(lambda: self.step_frames(-1))
        ctrl_layout.addWidget(self.btn_step_back)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_play.setToolTip("Play / Pause (Spacebar)")
        self.btn_play.clicked.connect(self.play_pause)
        ctrl_layout.addWidget(self.btn_play)

        self.btn_step_fwd = QPushButton("+1 ▶")
        self.btn_step_fwd.setToolTip("Step Forward 1 Frame (Right Arrow)")
        self.btn_step_fwd.clicked.connect(lambda: self.step_frames(1))
        ctrl_layout.addWidget(self.btn_step_fwd)

        self.btn_step_fwd_10 = QPushButton("+10 ⏩")
        self.btn_step_fwd_10.setToolTip("Step Forward 10 Frames (Shift + Right Arrow)")
        self.btn_step_fwd_10.clicked.connect(lambda: self.step_frames(10))
        ctrl_layout.addWidget(self.btn_step_fwd_10)

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

        # Left / Right arrows for single frame stepping
        shortcut_left = QShortcut(QKeySequence(Qt.Key_Left), self)
        shortcut_left.activated.connect(lambda: self.step_frames(-1))

        shortcut_right = QShortcut(QKeySequence(Qt.Key_Right), self)
        shortcut_right.activated.connect(lambda: self.step_frames(1))

        # Shift + Left / Right for 10-frame jumps
        shortcut_shift_left = QShortcut(QKeySequence(Qt.SHIFT | Qt.Key_Left), self)
        shortcut_shift_left.activated.connect(lambda: self.step_frames(-10))

        shortcut_shift_right = QShortcut(QKeySequence(Qt.SHIFT | Qt.Key_Right), self)
        shortcut_shift_right.activated.connect(lambda: self.step_frames(10))

        # Home / End for First / Last Frame
        shortcut_home = QShortcut(QKeySequence(Qt.Key_Home), self)
        shortcut_home.activated.connect(lambda: self.media_player.setPosition(0))

        shortcut_end = QShortcut(QKeySequence(Qt.Key_End), self)
        shortcut_end.activated.connect(lambda: self.media_player.setPosition(self.media_player.duration()))

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

    def step_frames(self, delta_frames: int):
        """Steps playback by delta_frames, pausing playback if running."""
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

        cur_ms = self.media_player.position()
        delta_ms = int(round(delta_frames * self.ms_per_frame))
        new_ms = max(0, min(self.media_player.duration(), cur_ms + delta_ms))
        self.media_player.setPosition(new_ms)

    def toggle_loop(self):
        self.is_looping = not self.is_looping
        self.btn_loop.setText(f"Loop: {'ON' if self.is_looping else 'OFF'}")

    def on_position_changed(self, position_ms: int):
        if not self.slider.isSliderDown():
            frame_offset = int(round(position_ms / self.ms_per_frame))
            self.slider.setValue(frame_offset)
        self.update_frame_label(position_ms)

    def on_duration_changed(self, duration_ms: int):
        total_frames = max(1, int(round(duration_ms / self.ms_per_frame)))
        self.slider.setRange(0, total_frames - 1)
        self.update_frame_label(self.media_player.position())

    def on_slider_scrubbed(self, frame_offset: int):
        target_ms = int(round(frame_offset * self.ms_per_frame))
        self.media_player.setPosition(target_ms)
        self.update_frame_label(target_ms)

    def update_frame_label(self, position_ms: int):
        cur_frame_offset = int(round(position_ms / self.ms_per_frame))
        curr_frame = self.frame_start + cur_frame_offset

        duration_ms = self.media_player.duration()
        total_frames = max(1, int(round(duration_ms / self.ms_per_frame)))
        end_frame = self.frame_start + total_frames - 1

        self.frame_label.setText(f"Frame: {curr_frame} / {end_frame}  [{cur_frame_offset + 1}/{total_frames}]")

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia and self.is_looping:
            self.media_player.setPosition(0)
            self.media_player.play()

    def closeEvent(self, event):
        self.media_player.stop()
        super().closeEvent(event)
