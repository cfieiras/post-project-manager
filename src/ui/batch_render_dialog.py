"""
Batch Render Dialog.
Executes background sequential rendering queue with Nuke CLI, active animated loader,
live queue tracking, and log output.
"""

import time
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QRadioButton,
    QSplitter, QTextEdit, QVBoxLayout, QWidget
)

from ..core.nuke_runner import NukeBatchRunner
from .theme import get_app_icon


class BatchRenderDialog(QDialog):
    renders_completed = Signal()

    def __init__(self, selected_shots: List[dict], parent=None):
        super().__init__(parent)
        self.selected_shots = selected_shots
        self.runner = NukeBatchRunner(self)
        self.start_time: Optional[float] = None

        self.setWindowTitle("Sequential Render Queue - Nuke")
        self.setWindowIcon(get_app_icon())
        self.resize(850, 560)
        self.setMinimumSize(720, 460)

        # Elapsed Timer
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.on_timer_tick)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # Header Bar
        header_bar = QHBoxLayout()
        self.info_lbl = QLabel(f"<b>Sequential Render Queue:</b> {len(self.selected_shots)} shot(s) in batch.")
        self.info_lbl.setStyleSheet("font-size: 13px; color: #4da6ff;")
        header_bar.addWidget(self.info_lbl)

        header_bar.addStretch()

        self.elapsed_lbl = QLabel("Elapsed: 00:00")
        self.elapsed_lbl.setStyleSheet("color: #a0a0a8; font-weight: bold;")
        header_bar.addWidget(self.elapsed_lbl)
        layout.addLayout(header_bar)

        # Target Selection Bar & Version Filter
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("<b>Default Target:</b>"))

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

        target_layout.addSpacing(16)
        target_layout.addWidget(QLabel("<b>Version:</b>"))
        self.version_combo = QComboBox()
        self.version_combo.addItem("Latest Version Only")
        self.version_combo.addItem("All Script Versions")

        # If a single shot is loaded, offer its specific versions directly
        if len(self.selected_shots) == 1:
            shot_versions = self.selected_shots[0].get("all_script_versions", [])
            for v in shot_versions:
                self.version_combo.addItem(f"Version: {v}")

        self.version_combo.currentIndexChanged.connect(self.rebuild_queue_list)
        self.rb_review.toggled.connect(self.rebuild_queue_list)
        self.rb_hires.toggled.connect(self.rebuild_queue_list)
        self.rb_both.toggled.connect(self.rebuild_queue_list)
        target_layout.addWidget(self.version_combo)

        target_layout.addStretch()
        layout.addLayout(target_layout)

        # Splitter: Queue List on Left, Live Console on Right
        splitter = QSplitter(Qt.Horizontal)

        # Left: Queue List
        queue_widget = QWidget()
        queue_layout = QVBoxLayout(queue_widget)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        queue_layout.setSpacing(4)
        queue_layout.addWidget(QLabel("<b>Sequential Queue:</b>"))

        self.queue_list = QListWidget()
        self.queue_list.setStyleSheet(
            "QListWidget { background-color: #16161a; border: 1px solid #33333e; border-radius: 4px; padding: 4px; }"
            "QListWidget::item { padding: 4px 6px; margin: 1px 0px; border-radius: 3px; }"
            "QListWidget::item:selected { background-color: #0078d4; color: #ffffff; }"
        )
        queue_layout.addWidget(self.queue_list)
        splitter.addWidget(queue_widget)

        # Right: Live Console Output
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(4)
        console_layout.addWidget(QLabel("<b>Nuke CLI Live Output:</b>"))

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; background-color: #121214;")
        console_layout.addWidget(self.console)
        splitter.addWidget(console_widget)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        layout.addWidget(splitter, stretch=1)

        # Progress & Status Feedback Area
        status_box = QVBoxLayout()
        status_box.setSpacing(4)

        status_header = QHBoxLayout()
        self.status_label = QLabel("Ready to start.")
        self.status_label.setStyleSheet("font-weight: bold; color: #ffffff;")
        status_header.addWidget(self.status_label)

        status_header.addStretch()

        self.batch_count_lbl = QLabel("0 / 0 Completed")
        self.batch_count_lbl.setStyleSheet("color: #a0a0aa;")
        status_header.addWidget(self.batch_count_lbl)
        status_box.addLayout(status_header)

        # Active Animated Spinner / Loader
        self.loader_bar = QProgressBar()
        self.loader_bar.setRange(0, 0)  # Continuous animated pulsing loader
        self.loader_bar.setTextVisible(False)
        self.loader_bar.setFixedHeight(5)
        self.loader_bar.setVisible(False)
        status_box.addWidget(self.loader_bar)

        # Overall Batch Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.selected_shots))
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        status_box.addWidget(self.progress_bar)

        layout.addLayout(status_box)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
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
        self.runner.job_finished.connect(self.on_single_job_finished)

        # Populate initial queue preview
        self.rebuild_queue_list()

    def _get_jobs_for_shot(self, shot: dict, target_write_node: Optional[str] = None) -> List[dict]:
        jobs = []
        target_id = self.btn_group.checkedId()
        ver_choice = self.version_combo.currentText()

        # Determine which scripts to render for this shot
        scripts_to_render: List[tuple] = []  # list of (version_label, script_path)

        all_scripts = shot.get("all_script_files", {})
        if ver_choice == "All Script Versions" and all_scripts:
            for v_str in shot.get("all_script_versions", sorted(all_scripts.keys())):
                scripts_to_render.append((v_str, all_scripts[v_str]))
        elif ver_choice.startswith("Version: ") and all_scripts:
            selected_v = ver_choice.replace("Version: ", "").strip()
            if selected_v in all_scripts:
                scripts_to_render.append((selected_v, all_scripts[selected_v]))
        else:
            # Latest version default
            latest_p = shot.get("latest_script_path")
            latest_v = shot.get("latest_script_version", "latest")
            if latest_p:
                scripts_to_render.append((latest_v, latest_p))

        for v_lbl, script_path in scripts_to_render:
            if target_write_node:
                jobs.append({
                    "shot_name": f"{shot['shot_name']} ({v_lbl})",
                    "script_path": script_path,
                    "write_node": target_write_node,
                    "frame_range": "1001,1100"
                })
            elif target_id == 1:
                jobs.append({
                    "shot_name": f"{shot['shot_name']} ({v_lbl})",
                    "script_path": script_path,
                    "write_node": "Write_REVIEW",
                    "frame_range": "1001,1100"
                })
            elif target_id == 2:
                jobs.append({
                    "shot_name": f"{shot['shot_name']} ({v_lbl})",
                    "script_path": script_path,
                    "write_node": "Write_HIRES",
                    "frame_range": "1001,1100"
                })
            else:
                jobs.append({
                    "shot_name": f"{shot['shot_name']} ({v_lbl}) [Hires]",
                    "script_path": script_path,
                    "write_node": "Write_HIRES",
                    "frame_range": "1001,1100"
                })
                jobs.append({
                    "shot_name": f"{shot['shot_name']} ({v_lbl}) [Review]",
                    "script_path": script_path,
                    "write_node": "Write_REVIEW",
                    "frame_range": "1001,1100"
                })

        return jobs

    def rebuild_queue_list(self):
        self.queue_list.clear()
        for s in self.selected_shots:
            for job in self._get_jobs_for_shot(s):
                item = QListWidgetItem(f"⏳ {job['shot_name']}  [{job['write_node']}]")
                self.queue_list.addItem(item)

    def on_timer_tick(self):
        if self.start_time:
            elapsed = int(time.time() - self.start_time)
            m, s = divmod(elapsed, 60)
            self.elapsed_lbl.setText(f"Elapsed: {m:02d}:{s:02d}")

    def enqueue_shots(
        self,
        shots: List[dict],
        target_write_node: Optional[str] = None,
        explicit_script_path: Optional[str] = None,
        explicit_version: Optional[str] = None
    ):
        """Dynamically appends shots to the sequential render queue without creating duplicate processes."""
        new_jobs = []
        for s in shots:
            if explicit_script_path:
                v_lbl = explicit_version or s.get("latest_script_version", "v001")
                wn = target_write_node or ("Write_REVIEW" if self.rb_review.isChecked() else "Write_HIRES")
                new_jobs.append({
                    "shot_name": f"{s['shot_name']} ({v_lbl})",
                    "script_path": explicit_script_path,
                    "write_node": wn,
                    "frame_range": "1001,1100"
                })
                item = QListWidgetItem(f"⏳ {s['shot_name']} ({v_lbl})  [{wn}]")
                self.queue_list.addItem(item)
            else:
                shot_jobs = self._get_jobs_for_shot(s, target_write_node=target_write_node)
                for j in shot_jobs:
                    new_jobs.append(j)
                    item = QListWidgetItem(f"⏳ {j['shot_name']}  [{j['write_node']}]")
                    self.queue_list.addItem(item)

        if self.runner.is_running():
            self.runner.append_jobs(new_jobs)
            self.progress_bar.setRange(0, self.runner.total_jobs)
            self.status_label.setText(f"⏳ Added {len(new_jobs)} job(s) to sequential queue. Running one-by-one...")
            self.batch_count_lbl.setText(f"{self.runner.current_idx} / {self.runner.total_jobs} Completed")
        else:
            self.selected_shots.extend(shots)
            self.start_rendering(predefined_jobs=new_jobs)

    def start_rendering(self, predefined_jobs: Optional[List[dict]] = None):
        if predefined_jobs:
            jobs = predefined_jobs
        else:
            jobs = []
            for s in self.selected_shots:
                jobs.extend(self._get_jobs_for_shot(s))

        if not jobs:
            self.status_label.setText("No valid Nuke scripts found to render.")
            QMessageBox.warning(
                self,
                "No Renders to Execute",
                "No valid Nuke scripts were found for the selected shot(s) and version filter.\n\n"
                "Please verify that the .nk comp scripts exist on disk."
            )
            return

        self.progress_bar.setRange(0, len(jobs))
        self.progress_bar.setValue(0)
        self.loader_bar.setVisible(True)
        self.btn_start.setEnabled(False)
        self.btn_close.setText("Cancel Render")

        self.start_time = time.time()
        self.timer.start()

        self.runner.start_batch(jobs)

    def on_progress(self, current: int, total: int, shot_name: str):
        self.progress_bar.setValue(current - 1)
        self.status_label.setText(f"🔄 Rendering [{current}/{total}]: {shot_name} ...")
        self.batch_count_lbl.setText(f"{current - 1} / {total} Completed")

        # Update visual status in queue list
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            if shot_name in item.text():
                item.setText(f"🔄 [Rendering] {shot_name}")
                self.queue_list.setCurrentItem(item)

    def on_single_job_finished(self, current_num: int, shot_name: str, success: bool, exit_code: int):
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            if shot_name in item.text():
                if success:
                    item.setText(f"✔ [Done] {shot_name}")
                    item.setForeground(QColor("#4caf50"))
                else:
                    item.setText(f"❌ [Failed] {shot_name} (code {exit_code})")
                    item.setForeground(QColor("#ef5350"))
                break

    def on_output(self, line: str):
        self.console.append(line.rstrip())
        # Parse frame progress if visible in line
        if "writing" in line.lower() or "frame" in line.lower():
            clean_line = line.strip()
            if len(clean_line) < 60:
                self.status_label.setText(f"🔄 {clean_line}")

    def on_finished(self, success: bool, msg: str):
        self.timer.stop()
        self.loader_bar.setVisible(False)
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.batch_count_lbl.setText(f"{self.progress_bar.maximum()} / {self.progress_bar.maximum()} Completed")
        self.btn_start.setEnabled(True)
        self.btn_close.setText("Done")

        if success:
            self.status_label.setText(f"✔ {msg}")
            QMessageBox.information(self, "Render Completed", msg)
        else:
            self.status_label.setText(f"❌ {msg}")
            QMessageBox.critical(
                self,
                "Render Failed / Errors Detected",
                f"{msg}\n\nPlease check the console output below for details."
            )

        self.renders_completed.emit()

    def closeEvent(self, event):
        if self.runner.is_running():
            self.runner.cancel()
        super().closeEvent(event)
