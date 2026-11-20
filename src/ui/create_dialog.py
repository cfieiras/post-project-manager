"""
Project Creation and Modification Dialog with Live Tree Preview.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QFormLayout, QSplitter, QMessageBox, QTextEdit
)

from ..core.pipeline import PipelineManager


class ProjectDialog(QDialog):
    project_created = Signal(str)

    def __init__(
        self,
        pipeline_manager: PipelineManager,
        root_dir: Path,
        edit_mode: bool = False,
        existing_meta: Optional[Dict[str, Any]] = None,
        project_path: Optional[Path] = None,
        parent=None
    ):
        super().__init__(parent)
        self.pm = pipeline_manager
        self.root_dir = root_dir
        self.edit_mode = edit_mode
        self.existing_meta = existing_meta or {}
        self.project_path = project_path

        self.setWindowTitle("Modify Project" if edit_mode else "Create New Post Project")
        self.resize(950, 700)
        self.setMinimumSize(850, 600)

        self.init_ui()
        self.populate_initial_data()
        self.update_preview()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Header Title
        title_label = QLabel("Project Architecture & Scaffolding" if not self.edit_mode else f"Modify Project: {self.project_path.name}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #4da6ff;")
        main_layout.addWidget(title_label)

        # Main Splitter (Left: Controls, Right: Live Tree Preview)
        splitter = QSplitter(Qt.Horizontal)

        # ----------------- LEFT WIDGET -----------------
        left_widget = QGroupBox("Configuration")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(10)

        # 1. Project Code / Name
        form_code = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. PRJ_COMMERCIAL_01")
        if self.edit_mode:
            self.name_input.setText(self.project_path.name)
            self.name_input.setEnabled(False)
        else:
            self.name_input.textChanged.connect(self.update_preview)
        form_code.addRow("Project Code:", self.name_input)
        left_layout.addLayout(form_code)

        # 2. Technical Settings (FPS, Resolution, Color)
        settings_group = QGroupBox("Project Settings (Nuke Root & Conform)")
        settings_form = QFormLayout(settings_group)
        settings_form.setSpacing(6)

        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["24.0", "25.0", "23.976", "29.97", "30.0", "50.0", "60.0"])
        settings_form.addRow("FPS:", self.fps_combo)

        self.res_combo = QComboBox()
        self.res_combo.addItems([
            "1920x1080 (HD_1080)",
            "3840x2160 (UHD_4K)",
            "2048x1080 (2K_DCI)",
            "4096x2160 (4K_DCI)",
            "2048x858 (2K_Scope)",
            "1998x1080 (2K_Flat)"
        ])
        settings_form.addRow("Resolution:", self.res_combo)

        self.color_combo = QComboBox()
        self.color_combo.addItems([
            "OCIO - ACES 1.2 (ACEScg)",
            "OCIO - ACES 1.3 (ACEScg)",
            "Nuke Default (Linear/sRGB)"
        ])
        settings_form.addRow("Color Management:", self.color_combo)

        # Frame Range
        frame_layout = QHBoxLayout()
        self.frame_start = QSpinBox()
        self.frame_start.setRange(0, 999999)
        self.frame_start.setValue(1001)
        self.frame_end = QSpinBox()
        self.frame_end.setRange(0, 999999)
        self.frame_end.setValue(1100)
        frame_layout.addWidget(QLabel("Start:"))
        frame_layout.addWidget(self.frame_start)
        frame_layout.addWidget(QLabel("End:"))
        frame_layout.addWidget(self.frame_end)
        settings_form.addRow("Frame Range:", frame_layout)

        left_layout.addWidget(settings_group)

        # 3. Active Modules
        modules_group = QGroupBox("Active Modules")
        modules_layout = QVBoxLayout(modules_group)
        self.module_checkboxes: Dict[str, QCheckBox] = {}

        modules_data = self.pm.template.get("modules", {})
        for mod_id, mod_info in modules_data.items():
            cb = QCheckBox(f"{mod_info.get('name', mod_id)} ({mod_id})")
            cb.setChecked(mod_info.get("enabled_by_default", False))
            cb.stateChanged.connect(self.update_preview)
            self.module_checkboxes[mod_id] = cb
            modules_layout.addWidget(cb)

        left_layout.addWidget(modules_group)

        # 4. Sequences & Shots Generator
        seq_group = QGroupBox("Sequences & Shots Breakdown")
        seq_layout = QVBoxLayout(seq_group)

        gen_controls = QHBoxLayout()
        self.seq_count_spin = QSpinBox()
        self.seq_count_spin.setRange(1, 20)
        self.seq_count_spin.setValue(1)

        self.shot_count_spin = QSpinBox()
        self.shot_count_spin.setRange(1, 50)
        self.shot_count_spin.setValue(3)

        btn_regen = QPushButton("Generate Shots")
        btn_regen.clicked.connect(self.generate_default_shots_text)

        gen_controls.addWidget(QLabel("Seqs:"))
        gen_controls.addWidget(self.seq_count_spin)
        gen_controls.addWidget(QLabel("Shots/Seq:"))
        gen_controls.addWidget(self.shot_count_spin)
        gen_controls.addWidget(btn_regen)
        seq_layout.addLayout(gen_controls)

        self.shots_edit = QTextEdit()
        self.shots_edit.setPlaceholderText("Format per line:\nsq010: sq010_sh010, sq010_sh020, sq010_sh030\nsq020: sq020_sh010")
        self.shots_edit.textChanged.connect(self.update_preview)
        seq_layout.addWidget(self.shots_edit)

        left_layout.addWidget(seq_group)
        splitter.addWidget(left_widget)

        # ----------------- RIGHT WIDGET (Live Tree Preview) -----------------
        right_widget = QGroupBox("Live Directory Tree Preview")
        right_layout = QVBoxLayout(right_widget)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Directory Structure & Scaffolding"])
        right_layout.addWidget(self.tree_widget)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        main_layout.addWidget(splitter)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        action_text = "Save Changes (Non-Destructive)" if self.edit_mode else "Create Project"
        self.btn_action = QPushButton(action_text)
        self.btn_action.setObjectName("primaryButton")
        self.btn_action.clicked.connect(self.on_submit)
        btn_layout.addWidget(self.btn_action)

        main_layout.addLayout(btn_layout)

    def populate_initial_data(self):
        if self.edit_mode and self.existing_meta:
            # Populate from existing meta
            active_mods = self.existing_meta.get("active_modules", [])
            for mod_id, cb in self.module_checkboxes.items():
                cb.setChecked(mod_id in active_mods)

            settings = self.existing_meta.get("project_settings", {})
            fps_val = str(settings.get("fps", "24.0"))
            idx = self.fps_combo.findText(fps_val)
            if idx >= 0:
                self.fps_combo.setCurrentIndex(idx)

            self.frame_start.setValue(settings.get("frame_start", 1001))
            self.frame_end.setValue(settings.get("frame_end", 1100))

            # Populate sequences text
            seqs = self.existing_meta.get("sequences", {})
            lines = []
            for s_name, s_shots in seqs.items():
                lines.append(f"{s_name}: {', '.join(s_shots)}")
            self.shots_edit.setPlainText("\n".join(lines))
        else:
            # Generate default text for 1 seq, 3 shots
            self.generate_default_shots_text()

    def generate_default_shots_text(self):
        seq_num = self.seq_count_spin.value()
        shots_per_seq = self.shot_count_spin.value()
        lines = []
        for s in range(1, seq_num + 1):
            seq_code = f"sq{s * 10:03d}"
            shot_codes = [f"{seq_code}_sh{shot * 10:03d}" for shot in range(1, shots_per_seq + 1)]
            lines.append(f"{seq_code}: {', '.join(shot_codes)}")
        self.shots_edit.setPlainText("\n".join(lines))

    def parse_sequences(self) -> Dict[str, List[str]]:
        """Parses the text box into a sequences dict."""
        text = self.shots_edit.toPlainText().strip()
        result = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            seq_name, shots_str = line.split(":", 1)
            seq_name = seq_name.strip().lower()
            shots = [s.strip().lower() for s in shots_str.split(",") if s.strip()]
            if seq_name and shots:
                result[seq_name] = shots
        return result

    def get_active_modules(self) -> List[str]:
        return [mod_id for mod_id, cb in self.module_checkboxes.items() if cb.isChecked()]

    def get_project_settings(self) -> Dict[str, Any]:
        fps_text = self.fps_combo.currentText()
        res_text = self.res_combo.currentText()
        color_text = self.color_combo.currentText()

        # Parse resolution
        raw_res = res_text.split(" ")[0]
        res_name = res_text.split("(")[1].replace(")", "") if "(" in res_text else "Custom"

        # Parse color
        if "ACES 1.2" in color_text:
            mgmt, ocio, space = "OCIO", "aces_1.2", "ACES - ACEScg"
        elif "ACES 1.3" in color_text:
            mgmt, ocio, space = "OCIO", "aces_1.3", "ACES - ACEScg"
        else:
            mgmt, ocio, space = "Nuke", "nuke-default", "linear"

        return {
            "fps": float(fps_text),
            "resolution": raw_res,
            "resolution_name": res_name,
            "color_management": mgmt,
            "ocio_config": ocio,
            "working_space": space,
            "frame_start": self.frame_start.value(),
            "frame_end": self.frame_end.value()
        }

    def update_preview(self):
        """Rebuilds the live QTreeWidget preview."""
        self.tree_widget.clear()
        prj_code = self.name_input.text().strip() or "PROJECT_CODE"
        active_mods = self.get_active_modules()
        sequences = self.parse_sequences()

        paths = self.pm.build_project_tree_preview(prj_code, active_mods, sequences)

        # Root Item
        root_item = QTreeWidgetItem([f"{prj_code}/"])
        root_item.setExpanded(True)
        self.tree_widget.addTopLevelItem(root_item)

        # Tree map to build nested hierarchy
        tree_map = {"": root_item}

        for path in paths:
            parts = path.split("/")
            curr_path = ""
            for i, part in enumerate(parts):
                parent_path = curr_path
                curr_path = f"{curr_path}/{part}" if curr_path else part

                if curr_path not in tree_map:
                    parent_item = tree_map[parent_path]
                    is_leaf = (i == len(parts) - 1)
                    item_text = f"{part}/" if is_leaf else f"{part}/"
                    item = QTreeWidgetItem([item_text])
                    parent_item.addChild(item)
                    tree_map[curr_path] = item

                    # Expand first two levels
                    if i < 2:
                        parent_item.setExpanded(True)
                        item.setExpanded(True)

    def on_submit(self):
        prj_code = self.name_input.text().strip()
        if not prj_code:
            QMessageBox.warning(self, "Validation Error", "Please specify a project code/name.")
            return

        sequences = self.parse_sequences()
        if not sequences:
            QMessageBox.warning(self, "Validation Error", "Please define at least one sequence and shot.")
            return

        active_mods = self.get_active_modules()
        settings = self.get_project_settings()

        if not self.edit_mode:
            # Create Project
            success, msg = self.pm.create_project(
                root_dir=self.root_dir,
                project_code=prj_code,
                active_modules=active_mods,
                sequences=sequences,
                project_settings=settings
            )
        else:
            # Update Project
            success, msg = self.pm.update_project(
                project_path=self.project_path,
                active_modules=active_mods,
                sequences=sequences,
                project_settings=settings
            )

        if success:
            QMessageBox.information(self, "Success", msg)
            self.project_created.emit(prj_code)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", msg)
