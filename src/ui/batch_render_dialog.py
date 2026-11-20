"""
Batch Render Dialog.
Executes background rendering queue with Nuke CLI and displays live progress and log output.
"""

from typing import List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QRadioButton, QTextEdit, QVBoxLayout
)

from ..core.nuke_runner import NukeBatchRunner


class BatchRenderDialog(QDialog):
    def __init__(self, selected_shots: List[dict], parent=None):
        super().__init__(parent)
        self.selected_shots = selected_shots
        self.runner = NukeBatchRunner(self)

        self.setWindowTitle("Batch Render Queue - Nuke")
        self.resize(750, 500)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        info_lbl = QLabel(f"<b>Batch Render Queue:</b> {len(self.selected_shots)} shots selected.")
        info_lbl.setStyleSheet("font-size: 13px; color: #4da6ff;")
        layout.addWidget(info_lbl)

        # Render Targets
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Render Output Target:"))

        self.btn_group = QButtonGroup(self)
        self.rb_review = QRadioButton("Review Only (Proxy MOV/MP4)")
        self.rb_review.setChecked(True)
        self.btn_group.addButton(self.rb_review, 1)
        target_layout.addWidget(self.rb_review)

        self.rb_hires = QRadioButton("Hires Only (EXR Master)")
        self.btn_group.addButton(self.rb_hires, 2)
        target_layout.addWidget(self.rb_hires)

        self.rb_both = QRadioButton("Both (Hires + Review)")
        self.btn_group.addButton(self.rb_both, 3)
        target_layout.addWidget(self.rb_both)

        target_layout.addStretch()
        layout.addLayout(target_layout)

        # Progress Bar & Status
        self.status_label = QLabel("Ready to start.")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.selected_shots))
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Log Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("font-family: Consolas; font-size: 11px; background-color: #121214;")
        layout.addWidget(self.console)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        self.btn_start = QPushButton("🚀 Start Render")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.clicked.connect(self.start_rendering)
        btn_layout.addWidget(self.btn_start)

        layout.addLayout(btn_layout)

        # Connect Runner Signals
        self.runner.progress_changed.connect(self.on_progress)
        self.runner.output_received.connect(self.on_output)
        self.runner.batch_finished.connect(self.on_finished)

    def start_rendering(self):
        jobs = []
        target_id = self.btn_group.checkedId()

        for s in self.selected_shots:
            script_path = s.get("latest_script_path")
            if not script_path:
                continue

            if target_id == 1:
                # Review Only
                jobs.append({
                    "shot_name": s["shot_name"],
                    "script_path": script_path,
                    "write_node": "Write_REVIEW",
                    "frame_range": "1001,1100"
                })
            elif target_id == 2:
                # Hires Only
                jobs.append({
                    "shot_name": s["shot_name"],
                    "script_path": script_path,
                    "write_node": "Write_HIRES",
                    "frame_range": "1001,1100"
                })
            else:
                # Both: queue Hires first, then Review
                jobs.append({
                    "shot_name": f"{s['shot_name']} (Hires)",
                    "script_path": script_path,
                    "write_node": "Write_HIRES",
                    "frame_range": "1001,1100"
                })
                jobs.append({
                    "shot_name": f"{s['shot_name']} (Review)",
                    "script_path": script_path,
                    "write_node": "Write_REVIEW",
                    "frame_range": "1001,1100"
                })

        self.progress_bar.setRange(0, len(jobs))
        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(False)
        self.console.clear()

        self.runner.start_batch(jobs)

    def on_progress(self, current: int, total: int, shot_name: str):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Rendering [{current}/{total}]: {shot_name}")

    def on_output(self, line: str):
        self.console.append(line.rstrip())

    def on_finished(self, success: bool, msg: str):
        self.status_label.setText(msg)
        self.btn_start.setEnabled(True)
        self.btn_close.setText("Done")

    def closeEvent(self, event):
        self.runner.cancel()
        super().closeEvent(event)
