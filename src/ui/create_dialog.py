"""
Project Creation and Modification Dialog with Live Tree Preview.
Clean, artist-friendly UI with visual sequence/shot management and custom resolution support.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QFormLayout, QSplitter, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget
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
        self.resize(1000, 720)
        self.setMinimumSize(900, 620)

        self.init_ui()
        self.populate_initial_data()
        self.update_preview()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Header Title
        title_label = QLabel(
            "Project Architecture & Scaffolding" if not self.edit_mode
            else f"Modify Project: {self.project_path.name}"
        )
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #4da6ff;")
        main_layout.addWidget(title_label)

        # Main Splitter (Left: Controls, Right: Live Tree Preview)
        splitter = QSplitter(Qt.Horizontal)

        # ----------------- LEFT WIDGET -----------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. Project Code / Name
        code_group = QGroupBox("Project Identification")
        code_form = QFormLayout(code_group)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. PRJ_COMMERCIAL_01")
        if self.edit_mode:
            self.name_input.setText(self.project_path.name)
            self.name_input.setEnabled(False)
        else:
            self.name_input.textChanged.connect(self.update_preview)
        code_form.addRow("Project Code:", self.name_input)
        left_layout.addWidget(code_group)

        # 2. Technical Settings (FPS, Resolution, Color)
        settings_group = QGroupBox("Project Settings (Nuke Root & Conform)")
        settings_form = QFormLayout(settings_group)
        settings_form.setSpacing(6)

        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["24.0", "25.0", "23.976", "29.97", "30.0", "50.0", "60.0"])
        settings_form.addRow("FPS:", self.fps_combo)

        # Resolution dropdown + Custom inputs
        self.res_combo = QComboBox()
        self.res_presets = [
            ("1920x1080 (HD_1080)", 1920, 1080),
            ("3840x2160 (UHD_4K)", 3840, 2160),
            ("2048x1080 (2K_DCI)", 2048, 1080),
            ("4096x2160 (4K_DCI)", 4096, 2160),
            ("2048x858 (2K_Scope)", 2048, 858),
            ("1998x1080 (2K_Flat)", 1998, 1080),
            ("Custom...", 1920, 1080)
        ]
        for label, _, _ in self.res_presets:
            self.res_combo.addItem(label)
        self.res_combo.currentIndexChanged.connect(self.on_resolution_changed)
        settings_form.addRow("Resolution:", self.res_combo)

        # Custom resolution input row
        self.custom_res_widget = QWidget()
        custom_res_layout = QHBoxLayout(self.custom_res_widget)
        custom_res_layout.setContentsMargins(0, 0, 0, 0)
        custom_res_layout.setSpacing(6)

        custom_res_layout.addWidget(QLabel("W:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(100, 16384)
        self.width_spin.setValue(1920)
        self.width_spin.setEnabled(False)
        custom_res_layout.addWidget(self.width_spin)

        custom_res_layout.addWidget(QLabel("H:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(100, 16384)
        self.height_spin.setValue(1080)
        self.height_spin.setEnabled(False)
        custom_res_layout.addWidget(self.height_spin)

        settings_form.addRow("Custom Dimensions:", self.custom_res_widget)

        self.color_combo = QComboBox()
        self.color_combo.addItems([
            "OCIO - ACES 1.2 (ACEScg)",
            "OCIO - ACES 1.3 (ACEScg)",
            "Nuke Default (Linear/sRGB)"
        ])
        settings_form.addRow("Color Management:", self.color_combo)

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

        # 4. Sequences & Shots Visual Management
        seq_group = QGroupBox("Sequences & Shots Management")
        seq_layout = QVBoxLayout(seq_group)
        seq_layout.setSpacing(8)

        # Table of sequences
        self.seq_table = QTableWidget()
        self.seq_table.setColumnCount(4)
        self.seq_table.setHorizontalHeaderLabels(["Sequence", "Shots", "Shots Generated Preview", ""])
        self.seq_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.seq_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.seq_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.seq_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.seq_table.verticalHeader().setVisible(False)
        self.seq_table.setSelectionMode(QTableWidget.NoSelection)
        seq_layout.addWidget(self.seq_table)

        btn_add_seq = QPushButton("+ Add Sequence")
        btn_add_seq.clicked.connect(self.add_sequence_row)
        seq_layout.addWidget(btn_add_seq)

        left_layout.addWidget(seq_group)
        splitter.addWidget(left_widget)

        # ----------------- RIGHT WIDGET (Live Tree Preview) -----------------
        right_widget = QGroupBox("Live Directory Tree Preview")
        right_layout = QVBoxLayout(right_widget)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Directory Structure & Scaffolding"])
        right_layout.addWidget(self.tree_widget)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 5)
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

    def on_resolution_changed(self, index: int):
        is_custom = (index == len(self.res_presets) - 1)
        self.width_spin.setEnabled(is_custom)
        self.height_spin.setEnabled(is_custom)

        if not is_custom:
            _, w, h = self.res_presets[index]
            self.width_spin.setValue(w)
            self.height_spin.setValue(h)

    def add_sequence_row(self, seq_name: Optional[str] = None, shot_count: int = 3):
        row = self.seq_table.rowCount()
        self.seq_table.insertRow(row)

        if not seq_name:
            # Calculate next default sequence name (sq010, sq020, etc.)
            seq_name = f"sq{(row + 1) * 10:03d}"

        # 1. Sequence Name Item
        seq_item = QTableWidgetItem(seq_name)
        seq_item.setTextAlignment(Qt.AlignCenter)
        self.seq_table.setItem(row, 0, seq_item)

        # 2. Shots Count Spinbox
        spin = QSpinBox()
        spin.setRange(1, 100)
        spin.setValue(shot_count)
        spin.valueChanged.connect(lambda: self.on_sequence_changed(row))
        self.seq_table.setCellWidget(row, 1, spin)

        # 3. Preview Item
        preview_item = QTableWidgetItem("")
        preview_item.setFlags(preview_item.flags() & ~Qt.ItemIsEditable)
        self.seq_table.setItem(row, 2, preview_item)

        # 4. Delete Button
        btn_del = QPushButton("✕")
        btn_del.setToolTip("Remove Sequence")
        btn_del.setStyleSheet("color: #ff5252; font-weight: bold; padding: 2px 8px;")
        btn_del.clicked.connect(lambda: self.remove_sequence_row(row))
        self.seq_table.setCellWidget(row, 3, btn_del)

        self.update_row_preview(row)
        self.update_preview()

    def remove_sequence_row(self, row: int):
        self.seq_table.removeRow(row)
        # Reconnect buttons to updated row indices
        for r in range(self.seq_table.rowCount()):
            btn = self.seq_table.cellWidget(r, 3)
            if btn:
                btn.clicked.disconnect()
                btn.clicked.connect(lambda curr_r=r: self.remove_sequence_row(curr_r))
        self.update_preview()

    def on_sequence_changed(self, row: int):
        self.update_row_preview(row)
        self.update_preview()

    def update_row_preview(self, row: int):
        seq_item = self.seq_table.item(row, 0)
        spin = self.seq_table.cellWidget(row, 1)
        preview_item = self.seq_table.item(row, 2)
        if seq_item and spin and preview_item:
            s_name = seq_item.text().strip().lower()
            count = spin.value()
            shots = [f"{s_name}_sh{i * 10:03d}" for i in range(1, count + 1)]
            preview_item.setText(", ".join(shots))

    def get_sequences(self) -> Dict[str, List[str]]:
        result = {}
        for row in range(self.seq_table.rowCount()):
            seq_item = self.seq_table.item(row, 0)
            spin = self.seq_table.cellWidget(row, 1)
            if seq_item and spin:
                s_name = seq_item.text().strip().lower()
                count = spin.value()
                if s_name:
                    result[s_name] = [f"{s_name}_sh{i * 10:03d}" for i in range(1, count + 1)]
        return result

    def populate_initial_data(self):
        if self.edit_mode and self.existing_meta:
            # Active modules
            active_mods = self.existing_meta.get("active_modules", [])
            for mod_id, cb in self.module_checkboxes.items():
                cb.setChecked(mod_id in active_mods)

            # Settings
            settings = self.existing_meta.get("project_settings", {})
            fps_val = str(settings.get("fps", "24.0"))
            idx = self.fps_combo.findText(fps_val)
            if idx >= 0:
                self.fps_combo.setCurrentIndex(idx)

            # Resolution
            res_str = settings.get("resolution", "1920x1080")
            matched_preset = False
            for i, (label, w, h) in enumerate(self.res_presets[:-1]):
                if f"{w}x{h}" == res_str:
                    self.res_combo.setCurrentIndex(i)
                    matched_preset = True
                    break
            if not matched_preset:
                self.res_combo.setCurrentIndex(len(self.res_presets) - 1)
                try:
                    w_s, h_s = res_str.split("x")
                    self.width_spin.setValue(int(w_s))
                    self.height_spin.setValue(int(h_s))
                except Exception:
                    pass

            # Existing sequences
            seqs = self.existing_meta.get("sequences", {})
            for s_name, shots in seqs.items():
                self.add_sequence_row(s_name, len(shots))
        else:
            # Add default 1 sequence with 3 shots
            self.add_sequence_row("sq010", 3)

    def get_active_modules(self) -> List[str]:
        return [mod_id for mod_id, cb in self.module_checkboxes.items() if cb.isChecked()]

    def get_project_settings(self) -> Dict[str, Any]:
        fps_text = self.fps_combo.currentText()
        color_text = self.color_combo.currentText()

        # Resolution
        width = self.width_spin.value()
        height = self.height_spin.value()
        res_str = f"{width}x{height}"

        res_idx = self.res_combo.currentIndex()
        if res_idx < len(self.res_presets) - 1:
            label, _, _ = self.res_presets[res_idx]
            res_name = label.split("(")[1].replace(")", "") if "(" in label else "Custom"
        else:
            res_name = f"Custom_{res_str}"

        # Color
        if "ACES 1.2" in color_text:
            mgmt, ocio, space = "OCIO", "aces_1.2", "ACES - ACEScg"
        elif "ACES 1.3" in color_text:
            mgmt, ocio, space = "OCIO", "aces_1.3", "ACES - ACEScg"
        else:
            mgmt, ocio, space = "Nuke", "nuke-default", "linear"

        return {
            "fps": float(fps_text),
            "resolution": res_str,
            "resolution_name": res_name,
            "color_management": mgmt,
            "ocio_config": ocio,
            "working_space": space,
            "frame_start": 1001,  # Default starter frame range (can be inferred from plate later)
            "frame_end": 1100
        }

    def update_preview(self):
        """Rebuilds the live QTreeWidget preview."""
        self.tree_widget.clear()
        prj_code = self.name_input.text().strip() or "PROJECT_CODE"
        active_mods = self.get_active_modules()
        sequences = self.get_sequences()

        paths = self.pm.build_project_tree_preview(prj_code, active_mods, sequences)

        # Root Item
        root_item = QTreeWidgetItem([f"{prj_code}/"])
        root_item.setExpanded(True)
        self.tree_widget.addTopLevelItem(root_item)

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

                    if i < 2:
                        parent_item.setExpanded(True)
                        item.setExpanded(True)

    def on_submit(self):
        prj_code = self.name_input.text().strip()
        if not prj_code:
            QMessageBox.warning(self, "Validation Error", "Please specify a project code/name.")
            return

        sequences = self.get_sequences()
        if not sequences:
            QMessageBox.warning(self, "Validation Error", "Please add at least one sequence.")
            return

        active_mods = self.get_active_modules()
        settings = self.get_project_settings()

        if not self.edit_mode:
            success, msg = self.pm.create_project(
                root_dir=self.root_dir,
                project_code=prj_code,
                active_modules=active_mods,
                sequences=sequences,
                project_settings=settings
            )
        else:
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
