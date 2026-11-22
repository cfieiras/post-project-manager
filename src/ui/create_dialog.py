"""
Project Creation and Modification Dialog with Live Tree Preview.
Clean, artist-friendly UI with visual sequence/shot management (Option B) and custom resolution support.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)

from ..core.pipeline import PipelineManager
from .theme import get_app_icon


MODULE_DISPLAY_NAMES = {
    "comp": "Compositing",
    "ai": "AI",
    "3d_dcc": "3D Traditional",
    "unreal": "Unreal Engine"
}


class SeqShotTreeWidget(QTreeWidget):
    """
    Hierarchical tree widget for Sequences and Shots management.
    Displays Sequences as expandable root items and Shots as clean child items.
    """
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Sequence & Shot Hierarchy"])
        self.header().setStretchLastSection(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.customContextMenuRequested.connect(self.on_context_menu)
        self.setStyleSheet(
            "QTreeWidget { background-color: #18181a; border: 1px solid #3d3d46; border-radius: 4px; padding: 4px; }"
            "QTreeWidget::item { padding: 4px 6px; margin: 1px 0px; border-radius: 3px; }"
            "QTreeWidget::item:hover { background-color: #282832; }"
            "QTreeWidget::item:selected { background-color: #0078d4; color: #ffffff; }"
        )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.remove_selected()
        elif event.key() == Qt.Key_F2:
            item = self.currentItem()
            if item:
                self.on_item_double_clicked(item, 0)
        else:
            super().keyPressEvent(event)

    def add_sequence(self, seq_name: str, shots: Optional[List[str]] = None) -> QTreeWidgetItem:
        clean_seq = seq_name.strip().lower()
        if not clean_seq:
            clean_seq = f"sq{(self.topLevelItemCount() + 1) * 10:03d}"

        if shots is None:
            shots = ["sh010", "sh020", "sh030"]

        clean_shots = []
        for s in shots:
            if s.startswith(f"{clean_seq}_"):
                clean_shots.append(s[len(f"{clean_seq}_"):])
            else:
                clean_shots.append(s)

        seq_item = QTreeWidgetItem(self)
        seq_item.setData(0, Qt.UserRole, {"type": "seq", "name": clean_seq})
        seq_item.setText(0, f"📁 {clean_seq}  ({len(clean_shots)} shots)")
        seq_item.setFlags(seq_item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        for s in clean_shots:
            shot_item = QTreeWidgetItem(seq_item)
            shot_item.setData(0, Qt.UserRole, {"type": "shot", "name": s, "seq": clean_seq})
            shot_item.setText(0, f"🎬 {s}")
            shot_item.setFlags(shot_item.flags() | Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        seq_item.setExpanded(True)
        self.changed.emit()
        return seq_item

    def get_data(self) -> Dict[str, List[str]]:
        result = {}
        for i in range(self.topLevelItemCount()):
            seq_item = self.topLevelItem(i)
            info = seq_item.data(0, Qt.UserRole)
            if not info:
                continue
            seq_name = info["name"]
            shot_list = []
            for j in range(seq_item.childCount()):
                shot_item = seq_item.child(j)
                shot_info = shot_item.data(0, Qt.UserRole)
                if shot_info:
                    shot_list.append(shot_info["name"])
            result[seq_name] = shot_list
        return result

    def add_shot_to_selected(self):
        item = self.currentItem()
        target_seq = None
        if item:
            info = item.data(0, Qt.UserRole)
            if info and info.get("type") == "seq":
                target_seq = item
            elif info and info.get("type") == "shot":
                target_seq = item.parent()

        if not target_seq and self.topLevelItemCount() > 0:
            target_seq = self.topLevelItem(self.topLevelItemCount() - 1)

        if target_seq:
            self.add_shot_to_seq(target_seq)

    def add_shot_to_seq(self, seq_item: QTreeWidgetItem):
        info = seq_item.data(0, Qt.UserRole)
        seq_name = info["name"]
        next_num = (seq_item.childCount() + 1) * 10
        shot_name = f"sh{next_num:03d}"

        shot_item = QTreeWidgetItem(seq_item)
        shot_item.setData(0, Qt.UserRole, {"type": "shot", "name": shot_name, "seq": seq_name})
        shot_item.setText(0, f"🎬 {shot_name}")
        seq_item.setText(0, f"📁 {seq_name}  ({seq_item.childCount()} shots)")
        seq_item.setExpanded(True)
        self.setCurrentItem(shot_item)
        self.changed.emit()

    def add_new_sequence(self):
        next_idx = (self.topLevelItemCount() + 1) * 10
        seq_name = f"sq{next_idx:03d}"
        item = self.add_sequence(seq_name)
        self.setCurrentItem(item)

    def rename_selected(self):
        item = self.currentItem()
        if item:
            self.on_item_double_clicked(item, 0)

    def on_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        info = item.data(0, Qt.UserRole)
        if not info:
            return

        if info["type"] == "seq":
            new_name, ok = QInputDialog.getText(
                self,
                "Rename Sequence",
                "Enter sequence identifier:",
                QLineEdit.Normal,
                info["name"]
            )
            if ok and new_name.strip():
                clean = new_name.strip().lower()
                info["name"] = clean
                item.setData(0, Qt.UserRole, info)
                item.setText(0, f"📁 {clean}  ({item.childCount()} shots)")
                # Update seq reference in all child shots
                for j in range(item.childCount()):
                    c_item = item.child(j)
                    c_info = c_item.data(0, Qt.UserRole)
                    if c_info:
                        c_info["seq"] = clean
                        c_item.setData(0, Qt.UserRole, c_info)
                self.changed.emit()

        elif info["type"] == "shot":
            new_name, ok = QInputDialog.getText(
                self,
                "Rename Shot",
                f"Enter shot identifier for '{info['seq']}':",
                QLineEdit.Normal,
                info["name"]
            )
            if ok and new_name.strip():
                clean = new_name.strip().lower()
                if clean.startswith(f"{info['seq']}_"):
                    clean = clean[len(f"{info['seq']}_"):]
                info["name"] = clean
                item.setData(0, Qt.UserRole, info)
                item.setText(0, f"🎬 {clean}")
                self.changed.emit()

    def remove_selected(self):
        item = self.currentItem()
        if item:
            self.remove_item(item)

    def remove_item(self, item: QTreeWidgetItem):
        info = item.data(0, Qt.UserRole)
        if not info:
            return

        if info["type"] == "seq":
            if self.topLevelItemCount() <= 1:
                QMessageBox.warning(self, "Action Denied", "At least one sequence is required in the project.")
                return
            reply = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Remove sequence '{info['name']}' and all its shots?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                idx = self.indexOfTopLevelItem(item)
                self.takeTopLevelItem(idx)
                self.changed.emit()

        elif info["type"] == "shot":
            parent = item.parent()
            if parent:
                parent.removeChild(item)
                p_info = parent.data(0, Qt.UserRole)
                parent.setText(0, f"📁 {p_info['name']}  ({parent.childCount()} shots)")
                self.changed.emit()

    def on_context_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)
        if item:
            info = item.data(0, Qt.UserRole)
            if info and info["type"] == "seq":
                menu.addAction("➕ Add Shot to Sequence", lambda: self.add_shot_to_seq(item))
                menu.addAction("✎ Rename Sequence", lambda: self.on_item_double_clicked(item, 0))
                if self.topLevelItemCount() > 1:
                    menu.addAction("✕ Remove Sequence", lambda: self.remove_item(item))
            elif info and info["type"] == "shot":
                menu.addAction("✎ Rename Shot", lambda: self.on_item_double_clicked(item, 0))
                menu.addAction("✕ Remove Shot", lambda: self.remove_item(item))
        else:
            menu.addAction("➕ Add Sequence", self.add_new_sequence)
        menu.exec(self.mapToGlobal(pos))


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
        self.setWindowIcon(get_app_icon())
        self.resize(1120, 880)
        self.setMinimumSize(980, 780)

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
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #4da6ff; padding: 2px 0px;")
        title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        main_layout.addWidget(title_label, stretch=0)

        # Main Splitter (Left: Controls, Right: Live Tree Preview)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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

        # Review Resolution Preset
        self.review_res_combo = QComboBox()
        self.review_res_combo.addItems([
            "Same as Project (100%)",
            "1920x1080 (HD_1080)",
            "1280x720 (720p HD)",
            "960x540 (Half HD - 540p)"
        ])
        settings_form.addRow("Review Resolution:", self.review_res_combo)

        # Review Video Codec & Format
        self.review_format_combo = QComboBox()
        self.review_format_combo.addItems([
            "MOV - Apple ProRes 422",
            "MOV - Apple ProRes 422 Proxy",
            "MP4 - H.264",
            "MOV - H.264"
        ])
        settings_form.addRow("Review Format & Codec:", self.review_format_combo)

        left_layout.addWidget(settings_group)

        # 3. Active Modules (Clean names without parentheses)
        modules_group = QGroupBox("Active Modules")
        modules_layout = QVBoxLayout(modules_group)
        self.module_checkboxes: Dict[str, QCheckBox] = {}

        modules_data = self.pm.template.get("modules", {})
        for mod_id, mod_info in modules_data.items():
            clean_label = MODULE_DISPLAY_NAMES.get(mod_id)
            if not clean_label:
                raw_name = mod_info.get("name", mod_id)
                clean_label = re.sub(r"\s*\(.*?\)", "", raw_name).strip()

            cb = QCheckBox(clean_label)
            cb.setChecked(mod_info.get("enabled_by_default", False))
            cb.stateChanged.connect(self.update_preview)
            self.module_checkboxes[mod_id] = cb
            modules_layout.addWidget(cb)

        left_layout.addWidget(modules_group)

        # 4. Sequences & Shots Tree Management
        seq_group = QGroupBox("Sequences & Shots Management")
        seq_layout = QVBoxLayout(seq_group)
        seq_layout.setSpacing(6)

        # Toolbar above the tree
        seq_bar = QHBoxLayout()
        seq_bar.setSpacing(6)

        btn_add_seq = QPushButton("+ Add Sequence")
        btn_add_seq.clicked.connect(lambda: self.seq_tree.add_new_sequence())
        seq_bar.addWidget(btn_add_seq)

        btn_add_shot = QPushButton("+ Add Shot")
        btn_add_shot.clicked.connect(lambda: self.seq_tree.add_shot_to_selected())
        seq_bar.addWidget(btn_add_shot)

        btn_rename = QPushButton("✎ Rename")
        btn_rename.clicked.connect(lambda: self.seq_tree.rename_selected())
        seq_bar.addWidget(btn_rename)

        btn_remove = QPushButton("✕ Remove")
        btn_remove.clicked.connect(lambda: self.seq_tree.remove_selected())
        seq_bar.addWidget(btn_remove)

        seq_bar.addStretch()
        seq_layout.addLayout(seq_bar)

        # Tree view
        self.seq_tree = SeqShotTreeWidget(parent=self)
        self.seq_tree.setMinimumHeight(240)
        self.seq_tree.changed.connect(self.update_preview)
        seq_layout.addWidget(self.seq_tree, stretch=1)

        left_layout.addWidget(seq_group, stretch=1)

        # Wrap left widget in a scroll area to guarantee clean layout on all displays
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        left_scroll.setWidget(left_widget)

        splitter.addWidget(left_scroll)

        # ----------------- RIGHT WIDGET (Live Tree Preview) -----------------
        right_widget = QGroupBox("Live Directory Tree Preview")
        right_layout = QVBoxLayout(right_widget)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Directory Structure & Scaffolding"])
        right_layout.addWidget(self.tree_widget)

        splitter.addWidget(right_widget)
        splitter.setHandleWidth(6)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)
        main_layout.addWidget(splitter, stretch=1)

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

    def get_sequences(self) -> Dict[str, List[str]]:
        return self.seq_tree.get_data()

    def populate_initial_data(self):
        if self.edit_mode and self.existing_meta:
            active_mods = self.existing_meta.get("active_modules", [])
            for mod_id, cb in self.module_checkboxes.items():
                cb.setChecked(mod_id in active_mods)

            settings = self.existing_meta.get("project_settings", {})
            fps_val = str(settings.get("fps", "24.0"))
            idx = self.fps_combo.findText(fps_val)
            if idx >= 0:
                self.fps_combo.setCurrentIndex(idx)

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

            # Restore Review settings
            rev_res = settings.get("review_resolution", "Same as Project (100%)")
            idx_rr = self.review_res_combo.findText(rev_res)
            if idx_rr >= 0:
                self.review_res_combo.setCurrentIndex(idx_rr)

            rev_codec = settings.get("review_codec", "Apple ProRes 422")
            rev_fmt = settings.get("review_format", "mov")
            target_text = f"{rev_fmt.upper()} - {rev_codec}"
            for i in range(self.review_format_combo.count()):
                if rev_codec.lower() in self.review_format_combo.itemText(i).lower():
                    self.review_format_combo.setCurrentIndex(i)
                    break

            seqs = self.existing_meta.get("sequences", {})
            for s_name, shots in seqs.items():
                self.seq_tree.add_sequence(s_name, shots)
        else:
            self.seq_tree.add_sequence("sq010", ["sh010", "sh020", "sh030"])

    def get_active_modules(self) -> List[str]:
        return [mod_id for mod_id, cb in self.module_checkboxes.items() if cb.isChecked()]

    def get_project_settings(self) -> Dict[str, Any]:
        fps_text = self.fps_combo.currentText()
        color_text = self.color_combo.currentText()

        width = self.width_spin.value()
        height = self.height_spin.value()
        res_str = f"{width}x{height}"

        res_idx = self.res_combo.currentIndex()
        if res_idx < len(self.res_presets) - 1:
            label, _, _ = self.res_presets[res_idx]
            res_name = label.split("(")[1].replace(")", "") if "(" in label else "Custom"
        else:
            res_name = f"Custom_{res_str}"

        if "ACES 1.2" in color_text:
            mgmt, ocio, space = "OCIO", "aces_1.2", "ACES - ACEScg"
        elif "ACES 1.3" in color_text:
            mgmt, ocio, space = "OCIO", "aces_1.3", "ACES - ACEScg"
        else:
            mgmt, ocio, space = "Nuke", "nuke-default", "linear"

        # Review settings
        rev_res = self.review_res_combo.currentText()
        rev_fmt_choice = self.review_format_combo.currentText()
        if "MP4" in rev_fmt_choice:
            review_format = "mp4"
            review_codec = "H.264"
        elif "Proxy" in rev_fmt_choice:
            review_format = "mov"
            review_codec = "Apple ProRes 422 Proxy"
        elif "H.264" in rev_fmt_choice:
            review_format = "mov"
            review_codec = "H.264"
        else:
            review_format = "mov"
            review_codec = "Apple ProRes 422"

        return {
            "fps": float(fps_text),
            "resolution": res_str,
            "resolution_name": res_name,
            "color_management": mgmt,
            "ocio_config": ocio,
            "working_space": space,
            "frame_start": 1001,
            "frame_end": 1100,
            "review_resolution": rev_res,
            "review_format": review_format,
            "review_codec": review_codec
        }

    def update_preview(self):
        """Rebuilds the live QTreeWidget preview."""
        self.tree_widget.clear()
        prj_code = self.name_input.text().strip() or "PROJECT_CODE"
        active_mods = self.get_active_modules()
        sequences = self.get_sequences()

        paths = self.pm.build_project_tree_preview(prj_code, active_mods, sequences)

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
