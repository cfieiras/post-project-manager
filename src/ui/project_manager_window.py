"""
Studio Project Manager Window (ShotGrid-Lite).
Next-generation production hub with visual thumbnails, DCC quick-launch badges,
modern status pills, smart filter chips, one-click outdated render, and keyboard shortcuts.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QProgressDialog, QPushButton,
    QStatusBar, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from ..core.config_manager import get_dcc_paths
from ..core.delivery_manager import DeliveryManager
from ..core.nuke_runner import find_nuke_executable
from ..core.shot_scanner import ShotScanner
from ..core.thumbnail_generator import ThumbnailManager
from .batch_render_dialog import BatchRenderDialog
from .delivery_setup_dialog import DeliverySetupDialog
from .player_dialog import ReviewPlayerDialog
from .studio_settings_dialog import StudioSettingsDialog
from .theme import get_app_icon, get_app_icon_pixmap


STATUS_STYLES = {
    "Approved": "background-color: #2e7d32; color: #ffffff; border-radius: 11px; font-weight: bold; padding: 2px 10px;",
    "In Progress": "background-color: #1565c0; color: #ffffff; border-radius: 11px; font-weight: bold; padding: 2px 10px;",
    "Pending Review": "background-color: #e65100; color: #ffffff; border-radius: 11px; font-weight: bold; padding: 2px 10px;",
    "Delivered": "background-color: #6a1b9a; color: #ffffff; border-radius: 11px; font-weight: bold; padding: 2px 10px;",
    "On Hold": "background-color: #c62828; color: #ffffff; border-radius: 11px; font-weight: bold; padding: 2px 10px;",
    "Not Started": "background-color: #424242; color: #b0b0b8; border-radius: 11px; font-weight: bold; padding: 2px 10px;"
}


class ProjectManagerWindow(QMainWindow):
    def __init__(self, project_path: Path, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.meta_file = self.project_path / "_pipeline" / "project_meta.json"
        self.shot_data_file = self.project_path / "_pipeline" / "shot_data.json"

        self.meta = self.load_json(self.meta_file)
        self.shot_data = self.load_json(self.shot_data_file)
        self.scanned_shots: List[Dict[str, Any]] = []
        self.active_status_filter = "All"
        self.all_selected_state = False
        self.render_queue_dialog: Optional[BatchRenderDialog] = None

        self.setWindowTitle(f"Project Manager - {self.project_path.name}")
        self.setWindowIcon(get_app_icon())
        self.resize(1340, 780)
        self.setMinimumSize(1050, 640)

        self.init_ui()
        self.setup_shortcuts()
        self.refresh_shots()

        # Check delivery folder setup after window is displayed
        QTimer.singleShot(150, self.check_initial_delivery_setup)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(14, 12, 14, 12)

        # 1. Top Metadata & Sequence Filter Bar
        top_bar = QHBoxLayout()

        logo_lbl = QLabel()
        logo_lbl.setPixmap(get_app_icon_pixmap(24))
        top_bar.addWidget(logo_lbl)

        settings = self.meta.get("project_settings", {})
        fps = settings.get("fps", 24.0)
        res = settings.get("resolution", "1920x1080")
        color = settings.get("ocio_config", "ACES")

        info_lbl = QLabel(
            f"<b style='font-size: 15px; color: #4da6ff;'>{self.project_path.name}</b> &nbsp;|&nbsp; "
            f"FPS: <b>{fps}</b> &nbsp;|&nbsp; Res: <b>{res}</b> &nbsp;|&nbsp; Color: <b>{color}</b>"
        )
        top_bar.addWidget(info_lbl)

        top_bar.addStretch()

        top_bar.addWidget(QLabel("<b>Sequence:</b>"))
        self.seq_filter_combo = QComboBox()
        self.seq_filter_combo.addItem("All Sequences")
        for seq_name in self.meta.get("sequences", {}).keys():
            self.seq_filter_combo.addItem(seq_name)
        self.seq_filter_combo.currentTextChanged.connect(self.apply_filter)
        top_bar.addWidget(self.seq_filter_combo)

        self.btn_settings = QPushButton("⚙ Settings")
        self.btn_settings.clicked.connect(self.open_studio_settings)
        top_bar.addWidget(self.btn_settings)

        btn_refresh = QPushButton("↻ Refresh Disk")
        btn_refresh.clicked.connect(self.refresh_shots)
        top_bar.addWidget(btn_refresh)

        main_layout.addLayout(top_bar)

        # 2. Smart Filters Bar (Search + Status Chips)
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search shots or notes...")
        self.search_input.setMaximumWidth(280)
        self.search_input.textChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.search_input)

        filter_bar.addWidget(QLabel("<b>Filter:</b>"))

        self.chip_group = QButtonGroup(self)
        self.chip_buttons: Dict[str, QPushButton] = {}

        chips = [
            ("All", "All"),
            ("Outdated", "⚠️ Outdated"),
            ("Pending Review", "🟠 Pending"),
            ("Approved", "🟢 Approved"),
            ("Delivered", "🟣 Delivered"),
            ("In Progress", "🔵 In Progress")
        ]

        for key, label in chips:
            btn = QPushButton(label)
            btn.setCheckable(True)
            if key == "All":
                btn.setChecked(True)
            btn.clicked.connect(lambda _, k=key: self.set_status_filter(k))
            self.chip_group.addButton(btn)
            self.chip_buttons[key] = btn
            filter_bar.addWidget(btn)

        filter_bar.addStretch()

        self.delivery_lbl = QLabel("Delivery: Not Configured")
        self.delivery_lbl.setStyleSheet("color: #b0b0b8; font-size: 11px;")
        self.update_delivery_label()
        filter_bar.addWidget(self.delivery_lbl)

        main_layout.addLayout(filter_bar)

        # 3. Main ShotGrid-Lite Table
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Select", "Thumbnail", "Shot & Scenes", "Status", "Notes & Supervisor Feedback",
            "Latest Review", "Hires Status", "Comp Sync", "Render Action", "Delivery"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Interactive)
        self.table.setColumnWidth(8, 200)
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Interactive)
        self.table.setColumnWidth(9, 240)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setDefaultSectionSize(82)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_shot_context_menu)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        main_layout.addWidget(self.table)

        # 4. Bottom Action Bar
        bottom_bar = QHBoxLayout()

        self.btn_select_all = QPushButton("☑ Select All")
        self.btn_select_all.clicked.connect(self.toggle_select_all)
        bottom_bar.addWidget(self.btn_select_all)

        self.btn_render_outdated = QPushButton("⚡ Render Outdated (0)")
        self.btn_render_outdated.setStyleSheet(
            "background-color: #ff9800; color: #101010; font-weight: bold; border-radius: 4px; padding: 6px 14px;"
        )
        self.btn_render_outdated.clicked.connect(self.on_render_outdated_clicked)
        bottom_bar.addWidget(self.btn_render_outdated)

        btn_batch_render = QPushButton("🚀 Batch Render Selected")
        btn_batch_render.setObjectName("primaryButton")
        btn_batch_render.clicked.connect(self.on_batch_render)
        bottom_bar.addWidget(btn_batch_render)

        btn_deliver = QPushButton("📦 Execute Client Delivery")
        btn_deliver.clicked.connect(self.on_execute_delivery)
        bottom_bar.addWidget(btn_deliver)

        bottom_bar.addSpacing(15)

        btn_open_shot = QPushButton("📁 Open Shot Folder")
        btn_open_shot.clicked.connect(self.open_selected_shot_folder)
        bottom_bar.addWidget(btn_open_shot)

        btn_open_delivery = QPushButton("📁 Open Delivery Folder")
        btn_open_delivery.clicked.connect(self.open_delivery_folder)
        bottom_bar.addWidget(btn_open_delivery)

        bottom_bar.addStretch()

        # Keyboard tips hint
        hint_lbl = QLabel("<span style='color: #70707a;'>Shortcuts: [Space] Play Review &nbsp;|&nbsp; [Enter] Launch Nuke</span>")
        bottom_bar.addWidget(hint_lbl)

        main_layout.addLayout(bottom_bar)

        # 5. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def setup_shortcuts(self):
        # Spacebar to play review of currently selected shot
        space_sc = QShortcut(QKeySequence(Qt.Key_Space), self.table)
        space_sc.activated.connect(self.on_space_pressed)

        # Enter to launch Nuke script of currently selected shot
        enter_sc = QShortcut(QKeySequence(Qt.Key_Return), self.table)
        enter_sc.activated.connect(self.on_enter_pressed)

    def on_space_pressed(self):
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            item = self.table.item(curr_row, 2)
            if item:
                shot = item.data(Qt.UserRole)
                if shot and shot.get("latest_review_path"):
                    self.open_player(shot)

    def on_enter_pressed(self):
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            item = self.table.item(curr_row, 2)
            if item:
                shot = item.data(Qt.UserRole)
                if shot and shot.get("latest_script_path"):
                    self.launch_file(Path(shot["latest_script_path"]))

    def on_header_clicked(self, logical_index: int):
        if logical_index == 0:
            self.toggle_select_all()

    def toggle_select_all(self):
        self.all_selected_state = not self.all_selected_state
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb:
                cb.setChecked(self.all_selected_state)
        self.btn_select_all.setText("☐ Deselect All" if self.all_selected_state else "☑ Select All")

    def set_status_filter(self, filter_key: str):
        self.active_status_filter = filter_key
        self.apply_filter()

    def load_json(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_shot_data(self):
        try:
            with open(self.shot_data_file, "w", encoding="utf-8") as f:
                json.dump(self.shot_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save shot data: {e}")

    def update_delivery_label(self):
        deliv = self.meta.get("delivery_dir")
        if deliv and Path(deliv).exists():
            self.delivery_lbl.setText(f"📁 <b>Delivery:</b> <span style='color: #4caf50;'>{Path(deliv).name}</span>")
            self.delivery_lbl.setToolTip(deliv)
        else:
            self.delivery_lbl.setText("📁 <b>Delivery:</b> <span style='color: #ff9800;'>Not Set</span>")

    def check_initial_delivery_setup(self):
        deliv = self.meta.get("delivery_dir")
        if not deliv or not Path(deliv).exists():
            dialog = DeliverySetupDialog(
                current_path=None,
                sequences=self.meta.get("sequences", {}),
                parent=self,
                is_first_time=True
            )
            if dialog.exec() == QDialog.Accepted and dialog.selected_path:
                self.meta["delivery_dir"] = dialog.selected_path
                with open(self.meta_file, "w", encoding="utf-8") as f:
                    json.dump(self.meta, f, indent=2, ensure_ascii=False)
                self.update_delivery_label()
        else:
            # Delivery folder is configured and exists on disk.
            # Check if project structure changed (new sequences/shots added).
            deliv_path = Path(deliv)
            sequences = self.meta.get("sequences", {})
            missing = DeliveryManager.get_missing_delivery_shots(deliv_path, sequences)
            if missing:
                missing_str = "\n".join([f"• {seq}/{shot}" for seq, shot in missing[:12]])
                if len(missing) > 12:
                    missing_str += f"\n... and {len(missing) - 12} more shot(s)."

                reply = QMessageBox.question(
                    self,
                    "Sync Delivery Structure",
                    f"Project structure changes were detected!\n\n"
                    f"The following {len(missing)} shot(s) are not yet scaffolded in your client delivery folder:\n"
                    f"{missing_str}\n\n"
                    f"Delivery Root:\n{deliv_path}\n\n"
                    f"Would you like to sync and update the delivery directory structure now?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self._sync_delivery_folder_with_progress(deliv_path, sequences)

    def _sync_delivery_folder_with_progress(self, delivery_path: Path, sequences: Dict[str, List[str]]):
        total_shots = sum(len(shots) for shots in sequences.values())
        progress_dlg = QProgressDialog(
            "Syncing delivery folder structure...",
            "Cancel",
            0,
            total_shots,
            self
        )
        progress_dlg.setWindowTitle("Updating Delivery Structure")
        progress_dlg.setWindowModality(Qt.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(0)
        QApplication.processEvents()

        def on_sync_progress(cur: int, total: int, label: str):
            if progress_dlg.wasCanceled():
                return
            progress_dlg.setValue(cur)
            progress_dlg.setLabelText(f"[{cur}/{total}] {label}")
            QApplication.processEvents()

        try:
            success, msg = DeliveryManager.setup_delivery_folder(
                delivery_path=delivery_path,
                sequences=sequences,
                progress_callback=on_sync_progress
            )
        finally:
            progress_dlg.close()

        if success:
            QMessageBox.information(
                self,
                "Delivery Sync Complete",
                f"Client delivery directory structure successfully updated:\n\n{delivery_path}"
            )
            self.update_delivery_label()
        else:
            QMessageBox.warning(self, "Delivery Sync Error", f"Failed to update delivery structure:\n{msg}")

    def open_studio_settings(self):
        dialog = StudioSettingsDialog(
            current_delivery_path=self.meta.get("delivery_dir"),
            sequences=self.meta.get("sequences", {}),
            project_settings=self.meta.get("project_settings"),
            parent=self
        )
        if dialog.exec() == QDialog.Accepted:
            changed = False
            if dialog.selected_delivery_path:
                self.meta["delivery_dir"] = dialog.selected_delivery_path
                changed = True
            if dialog.updated_project_settings:
                self.meta["project_settings"] = dialog.updated_project_settings
                changed = True

            if changed:
                with open(self.meta_file, "w", encoding="utf-8") as f:
                    json.dump(self.meta, f, indent=2, ensure_ascii=False)
                self.update_delivery_label()
                self.refresh_shots()

    def open_delivery_setup(self):
        self.open_studio_settings()

    def get_delivered_versions_for_shot(self, shot: Dict[str, Any]) -> List[str]:
        """Returns a list of versions already delivered for this shot on disk or in metadata."""
        seq = shot.get("seq_name", "")
        shot_name = shot.get("shot_name", "")
        deliv_dir_str = self.meta.get("delivery_dir")
        delivered = []
        if deliv_dir_str and Path(deliv_dir_str).exists():
            shot_deliv_path = Path(deliv_dir_str) / seq / shot_name
            if shot_deliv_path.exists():
                for v_dir in sorted(shot_deliv_path.glob("v*"), reverse=True):
                    if v_dir.is_dir():
                        rev_files = list((v_dir / "review").glob("*")) if (v_dir / "review").exists() else []
                        hires_files = list((v_dir / "hires").glob("*")) if (v_dir / "hires").exists() else []
                        if any(f.is_file() for f in rev_files) or any(f.is_file() for f in hires_files):
                            delivered.append(v_dir.name)
        # Also check saved shot_data
        k = f"{seq}_{shot_name}"
        saved_ver = self.shot_data.get(k, {}).get("last_delivered_version")
        if saved_ver and saved_ver not in delivered:
            delivered.append(saved_ver)
        return delivered

    def refresh_shots(self):
        sequences = self.meta.get("sequences", {})
        self.scanned_shots = ShotScanner.scan_all_shots(self.project_path, sequences)

        # Update outdated button count
        outdated_count = sum(1 for s in self.scanned_shots if s.get("is_outdated"))
        self.btn_render_outdated.setText(f"⚡ Render Outdated ({outdated_count})")
        self.btn_render_outdated.setEnabled(outdated_count > 0)

        # Update chip counts
        for key, btn in self.chip_buttons.items():
            if key == "All":
                btn.setText(f"All ({len(self.scanned_shots)})")
            elif key == "Outdated":
                btn.setText(f"⚠️ Outdated ({outdated_count})")
            else:
                count = sum(1 for s in self.scanned_shots if self.shot_data.get(f"{s['seq_name']}_{s['shot_name']}", {}).get("status") == key)
                short_name = key.split()[0]
                btn.setText(f"{short_name} ({count})")

        self.apply_filter()

    def apply_filter(self):
        selected_seq = self.seq_filter_combo.currentText()
        query = self.search_input.text().strip().lower()

        filtered = []
        for s in self.scanned_shots:
            shot_key = f"{s['seq_name']}_{s['shot_name']}"
            saved_info = self.shot_data.get(shot_key, {})
            status = saved_info.get("status", "Not Started")
            notes = saved_info.get("notes", "").lower()

            # Sequence match
            if selected_seq != "All Sequences" and s["seq_name"] != selected_seq:
                continue

            # Search match
            if query and (query not in s["shot_name"].lower() and query not in notes):
                continue

            # Status Chip filter
            if self.active_status_filter == "Outdated":
                if not s.get("is_outdated"):
                    continue
            elif self.active_status_filter != "All":
                if status != self.active_status_filter:
                    continue

            filtered.append(s)

        self.populate_table(filtered)

    def populate_table(self, shots: List[Dict[str, Any]]):
        self.table.setRowCount(len(shots))

        for row, shot in enumerate(shots):
            shot_key = f"{shot['seq_name']}_{shot['shot_name']}"
            saved_info = self.shot_data.get(shot_key, {})

            # 0. Selection Checkbox
            cb_item = QCheckBox()
            cb_item.setStyleSheet("margin-left: 8px;")
            self.table.setCellWidget(row, 0, cb_item)

            # 1. Visual Poster Thumbnail
            thumb_pixmap = ThumbnailManager.get_thumbnail(self.project_path, shot, width=120, height=68)
            thumb_btn = QPushButton()
            thumb_btn.setFixedSize(120, 68)
            thumb_btn.setIcon(thumb_pixmap)
            thumb_btn.setIconSize(thumb_pixmap.size())
            thumb_btn.setStyleSheet("border: 1px solid #2e2e38; border-radius: 4px; background: transparent; padding: 0;")
            thumb_btn.setToolTip("Click to play review in integrated player" if shot.get("latest_review_path") else "No review video yet")
            if shot.get("latest_review_path"):
                thumb_btn.clicked.connect(lambda _, s=shot: self.open_player(s))
            self.table.setCellWidget(row, 1, thumb_btn)

            # 2. Shot ID & DCC Quick-Launch Badges
            shot_widget = QWidget()
            sw_layout = QVBoxLayout(shot_widget)
            sw_layout.setContentsMargins(6, 4, 6, 4)
            sw_layout.setSpacing(4)

            shot_name_lbl = QLabel(f"<b>{shot['shot_name']}</b>")
            shot_name_lbl.setStyleSheet("font-size: 13px; color: #ffffff;")
            sw_layout.addWidget(shot_name_lbl)

            # DCC Badges Row
            badges_layout = QHBoxLayout()
            badges_layout.setSpacing(4)

            shot_dir = Path(shot.get("shot_dir", ""))
            self.add_dcc_badges(shot_dir, badges_layout)
            sw_layout.addLayout(badges_layout)

            # Store shot data in hidden item
            item_shot = QTableWidgetItem("")
            item_shot.setData(Qt.UserRole, shot)
            self.table.setItem(row, 2, item_shot)
            self.table.setCellWidget(row, 2, shot_widget)

            # 3. Status Pill Dropdown
            status_combo = QComboBox()
            for st in STATUS_STYLES.keys():
                status_combo.addItem(st)

            current_status = saved_info.get("status", "Not Started")
            idx = status_combo.findText(current_status)
            if idx >= 0:
                status_combo.setCurrentIndex(idx)
            self.apply_status_pill_style(status_combo, current_status)
            status_combo.currentTextChanged.connect(
                lambda val, k=shot_key, sc=status_combo: self.on_status_changed(k, val, sc)
            )
            self.table.setCellWidget(row, 3, status_combo)

            # 4. Notes Multiline TextEdit (Wraps lines downwards)
            notes_edit = QPlainTextEdit(saved_info.get("notes", ""))
            notes_edit.setPlaceholderText("Add notes...")
            notes_edit.setTabChangesFocus(True)
            notes_edit.setStyleSheet(
                "QPlainTextEdit { background-color: #18181a; border: 1px solid #33333e; "
                "border-radius: 4px; padding: 4px; color: #e0e0e0; font-size: 11px; }"
                "QPlainTextEdit:focus { border: 1px solid #4da6ff; }"
            )
            notes_edit.textChanged.connect(
                lambda k=shot_key, ne=notes_edit: self.on_notes_changed(k, ne.toPlainText())
            )
            self.table.setCellWidget(row, 4, notes_edit)

            # 5. Latest Review Version
            rev_ver = shot.get("latest_review_version") or "None"
            item_rev = QTableWidgetItem(rev_ver)
            item_rev.setTextAlignment(Qt.AlignCenter)
            if rev_ver != "None":
                item_rev.setForeground(QColor("#4caf50"))
            else:
                item_rev.setForeground(QColor("#757575"))
            self.table.setItem(row, 5, item_rev)

            # 6. Hires Status
            hires_ver = shot.get("latest_hires_version")
            if hires_ver:
                item_hires = QTableWidgetItem(f"🟢 {hires_ver} Ready")
                item_hires.setForeground(QColor("#4caf50"))
            else:
                item_hires = QTableWidgetItem("🔴 Missing")
                item_hires.setForeground(QColor("#ef5350"))
            item_hires.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 6, item_hires)

            # 7. Comp Sync Status
            item_sync = QTableWidgetItem(shot["sync_message"])
            item_sync.setTextAlignment(Qt.AlignCenter)
            if shot.get("is_outdated"):
                item_sync.setForeground(QColor("#ffb74d"))
            else:
                item_sync.setForeground(QColor("#81c784"))
            self.table.setItem(row, 7, item_sync)

            # 8. Render Action Buttons (Explicit Version Indication)
            render_widget = QWidget()
            rw_layout = QHBoxLayout(render_widget)
            rw_layout.setContentsMargins(2, 2, 2, 2)
            rw_layout.setSpacing(4)

            script_ver = shot.get("latest_script_version") or "v001"
            btn_r_rev = QPushButton(f"▶ {script_ver}")
            btn_r_rev.setToolTip(f"Render Review for {script_ver}")
            btn_r_rev.clicked.connect(lambda _, s=shot: self.render_single_shot(s, "Write_REVIEW"))
            rw_layout.addWidget(btn_r_rev)

            btn_r_hires = QPushButton(f"⚡ {script_ver}")
            btn_r_hires.setToolTip(f"Render Hires EXR for {script_ver}")
            btn_r_hires.clicked.connect(lambda _, s=shot: self.render_single_shot(s, "Write_HIRES"))
            rw_layout.addWidget(btn_r_hires)
            self.table.setCellWidget(row, 8, render_widget)

            # 9. Delivery Version Combo & Check + Delivered Status Info
            deliv_widget = QWidget()
            dw_layout = QVBoxLayout(deliv_widget)
            dw_layout.setContentsMargins(4, 2, 4, 2)
            dw_layout.setSpacing(2)

            top_row = QWidget()
            top_layout = QHBoxLayout(top_row)
            top_layout.setContentsMargins(0, 0, 0, 0)
            top_layout.setSpacing(6)

            cb_deliver = QCheckBox("Deliver")
            cb_deliver.setChecked(saved_info.get("marked_for_delivery", False))

            combo_deliv_ver = QComboBox()
            all_vers = sorted(list(set(
                list(shot.get("all_review_versions", {}).keys()) +
                shot.get("all_hires_versions", []) +
                shot.get("all_script_versions", [])
            )), reverse=True)
            if not all_vers:
                all_vers = ["v001"]
            for v in all_vers:
                combo_deliv_ver.addItem(v)

            saved_ver = saved_info.get("delivery_version") or shot.get("latest_script_version") or shot.get("latest_review_version")
            if saved_ver and saved_ver in all_vers:
                combo_deliv_ver.setCurrentText(saved_ver)

            cb_deliver.stateChanged.connect(
                lambda state, k=shot_key, cv=combo_deliv_ver: self.on_delivery_toggled(k, state, cv.currentText())
            )
            combo_deliv_ver.currentTextChanged.connect(
                lambda val, k=shot_key, cb=cb_deliver: self.on_delivery_toggled(k, cb.isChecked(), val)
            )

            top_layout.addWidget(cb_deliver)
            top_layout.addWidget(combo_deliv_ver)
            dw_layout.addWidget(top_row)

            # Delivered status indicator
            delivered_vers = self.get_delivered_versions_for_shot(shot)
            bottom_row = QHBoxLayout()
            bottom_row.setContentsMargins(0, 0, 0, 0)
            bottom_row.setSpacing(4)

            lbl_deliv_title = QLabel("Delivered:")
            lbl_deliv_title.setStyleSheet("color: #888892; font-size: 10px;")
            bottom_row.addWidget(lbl_deliv_title)

            if delivered_vers:
                deliv_txt = ", ".join(delivered_vers)
                lbl_deliv_val = QLabel(f"✔ {deliv_txt}")
                lbl_deliv_val.setStyleSheet(
                    "background-color: #2b3a32; color: #81c784; border: 1px solid #388e3c; "
                    "border-radius: 3px; font-weight: bold; font-size: 10px; padding: 1px 4px;"
                )
            else:
                lbl_deliv_val = QLabel("None")
                lbl_deliv_val.setStyleSheet("color: #757575; font-size: 10px; padding: 1px 2px;")

            bottom_row.addWidget(lbl_deliv_val)
            bottom_row.addStretch()
            dw_layout.addLayout(bottom_row)

            self.table.setCellWidget(row, 9, deliv_widget)

        self.status_bar.showMessage(f"Displaying {len(shots)} of {len(self.scanned_shots)} shots.")

    def add_dcc_badges(self, shot_dir: Path, layout: QHBoxLayout):
        """Adds compact, clickable quick-launch badges for detected DCC files."""
        # 1. Nuke
        comp_scripts_dir = shot_dir / "comp" / "scripts"
        if comp_scripts_dir.exists():
            nk_files = sorted(list(comp_scripts_dir.glob("*.nk")), reverse=True)
            if nk_files:
                btn_nk = QPushButton("NK")
                btn_nk.setToolTip(f"Open Nuke: {nk_files[0].name}")
                btn_nk.setStyleSheet("background-color: #e65100; color: #ffffff; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 3px;")
                btn_nk.clicked.connect(lambda _, f=nk_files[0]: self.launch_file(f))
                layout.addWidget(btn_nk)

            # After Effects
            aep_files = sorted(list(comp_scripts_dir.glob("*.aep")), reverse=True)
            if aep_files:
                btn_ae = QPushButton("AE")
                btn_ae.setToolTip(f"Open After Effects: {aep_files[0].name}")
                btn_ae.setStyleSheet("background-color: #7b1fa2; color: #ffffff; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 3px;")
                btn_ae.clicked.connect(lambda _, f=aep_files[0]: self.launch_file(f))
                layout.addWidget(btn_ae)

        # 2. 3D DCC Scenes
        scenes_3d_dir = shot_dir / "3d" / "scenes"
        if scenes_3d_dir.exists():
            # Blender
            blend_files = sorted(list(scenes_3d_dir.glob("*.blend")), reverse=True)
            if blend_files:
                btn_bl = QPushButton("BL")
                btn_bl.setToolTip(f"Open Blender: {blend_files[0].name}")
                btn_bl.setStyleSheet("background-color: #f57c00; color: #ffffff; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 3px;")
                btn_bl.clicked.connect(lambda _, f=blend_files[0]: self.launch_file(f))
                layout.addWidget(btn_bl)

            # Maya
            maya_files = sorted(list(scenes_3d_dir.glob("*.ma")) + list(scenes_3d_dir.glob("*.mb")), reverse=True)
            if maya_files:
                btn_my = QPushButton("MY")
                btn_my.setToolTip(f"Open Maya: {maya_files[0].name}")
                btn_my.setStyleSheet("background-color: #0097a7; color: #ffffff; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 3px;")
                btn_my.clicked.connect(lambda _, f=maya_files[0]: self.launch_file(f))
                layout.addWidget(btn_my)

            # Houdini
            hip_files = sorted(list(scenes_3d_dir.glob("*.hip*")), reverse=True)
            if hip_files:
                btn_hd = QPushButton("HD")
                btn_hd.setToolTip(f"Open Houdini: {hip_files[0].name}")
                btn_hd.setStyleSheet("background-color: #d84315; color: #ffffff; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 3px;")
                btn_hd.clicked.connect(lambda _, f=hip_files[0]: self.launch_file(f))
                layout.addWidget(btn_hd)

            # Cinema 4D
            c4d_files = sorted(list(scenes_3d_dir.glob("*.c4d")), reverse=True)
            if c4d_files:
                btn_c4d = QPushButton("C4D")
                btn_c4d.setToolTip(f"Open Cinema 4D: {c4d_files[0].name}")
                btn_c4d.setStyleSheet("background-color: #1976d2; color: #ffffff; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 3px;")
                btn_c4d.clicked.connect(lambda _, f=c4d_files[0]: self.launch_file(f))
                layout.addWidget(btn_c4d)

        # 3. Unreal Engine
        ue_dir = self.project_path / "unreal_projects"
        if ue_dir.exists():
            uprojects = list(ue_dir.glob("*/*.uproject"))
            if uprojects:
                btn_ue = QPushButton("UE")
                btn_ue.setToolTip(f"Open Unreal Engine: {uprojects[0].name}")
                btn_ue.setStyleSheet("background-color: #0288d1; color: #ffffff; font-size: 9px; font-weight: bold; padding: 1px 5px; border-radius: 3px;")
                btn_ue.clicked.connect(lambda _, f=uprojects[0]: self.launch_file(f))
                layout.addWidget(btn_ue)

        layout.addStretch()

    def apply_status_pill_style(self, combo: QComboBox, status: str):
        style = STATUS_STYLES.get(status, STATUS_STYLES["Not Started"])
        combo.setStyleSheet(style)

    def on_status_changed(self, shot_key: str, status: str, combo: QComboBox):
        self.apply_status_pill_style(combo, status)
        if shot_key not in self.shot_data:
            self.shot_data[shot_key] = {}
        self.shot_data[shot_key]["status"] = status
        self.save_shot_data()

    def on_notes_changed(self, shot_key: str, notes: str):
        if shot_key not in self.shot_data:
            self.shot_data[shot_key] = {}
        self.shot_data[shot_key]["notes"] = notes
        self.save_shot_data()

    def on_delivery_toggled(self, shot_key: str, is_checked: bool, version: str):
        if shot_key not in self.shot_data:
            self.shot_data[shot_key] = {}
        self.shot_data[shot_key]["marked_for_delivery"] = bool(is_checked)
        self.shot_data[shot_key]["delivery_version"] = version
        self.save_shot_data()

    def open_player(self, shot: Dict[str, Any]):
        rev_dict = shot.get("all_review_versions", {})
        latest_v = shot.get("latest_review_version", "v001")
        if not rev_dict:
            QMessageBox.information(self, "No Renders", "No review renders found for this shot.")
            return

        settings = self.meta.get("project_settings", {})
        fps = float(settings.get("fps", 24.0))
        frame_start = int(settings.get("frame_start", 1001))

        dialog = ReviewPlayerDialog(
            shot_name=shot["shot_name"],
            review_versions=rev_dict,
            initial_version=latest_v,
            fps=fps,
            frame_start=frame_start,
            parent=self
        )
        dialog.exec()

    def get_selected_shots(self) -> List[Dict[str, Any]]:
        selected = []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb and cb.isChecked():
                item = self.table.item(row, 2)
                if item:
                    selected.append(item.data(Qt.UserRole))
        return selected

    def _queue_render_jobs(
        self,
        shots: List[Dict[str, Any]],
        write_node: Optional[str] = None,
        explicit_script_path: Optional[str] = None,
        explicit_version: Optional[str] = None
    ):
        """Enqueues shots to the central sequential render dialog, avoiding multiple simultaneous Nuke runs."""
        valid_shots = [s for s in shots if s.get("latest_script_path") or explicit_script_path]
        if not valid_shots:
            QMessageBox.warning(self, "Missing Scripts", "No Nuke script found for the selected shot(s).")
            return

        if self.render_queue_dialog is None or not self.render_queue_dialog.isVisible():
            self.render_queue_dialog = BatchRenderDialog(valid_shots, parent=self)
            self.render_queue_dialog.renders_completed.connect(self.refresh_shots)
            if write_node == "Write_REVIEW":
                self.render_queue_dialog.rb_review.setChecked(True)
            elif write_node == "Write_HIRES":
                self.render_queue_dialog.rb_hires.setChecked(True)
            self.render_queue_dialog.show()
            self.render_queue_dialog.enqueue_shots(
                valid_shots,
                target_write_node=write_node,
                explicit_script_path=explicit_script_path,
                explicit_version=explicit_version
            )
        else:
            self.render_queue_dialog.enqueue_shots(
                valid_shots,
                target_write_node=write_node,
                explicit_script_path=explicit_script_path,
                explicit_version=explicit_version
            )
            self.render_queue_dialog.raise_()
            self.render_queue_dialog.activateWindow()

    def on_render_outdated_clicked(self):
        outdated_shots = [s for s in self.scanned_shots if s.get("is_outdated")]
        if not outdated_shots:
            QMessageBox.information(self, "Up to Date", "All shots are currently up to date!")
            return
        self._queue_render_jobs(outdated_shots)

    def on_batch_render(self):
        selected = self.get_selected_shots()
        if not selected:
            QMessageBox.information(self, "Selection Required", "Please select at least one shot via the checkbox.")
            return
        self._queue_render_jobs(selected)

    def render_single_shot(
        self,
        shot: Dict[str, Any],
        write_node: str,
        explicit_script_path: Optional[str] = None,
        explicit_version: Optional[str] = None
    ):
        target_path = explicit_script_path or shot.get("latest_script_path")
        if not target_path:
            QMessageBox.warning(self, "Missing Script", f"No Nuke script found for {shot['shot_name']}.")
            return
        self._queue_render_jobs(
            [shot],
            write_node=write_node,
            explicit_script_path=target_path,
            explicit_version=explicit_version
        )

    def render_all_versions_of_shot(self, shot: Dict[str, Any]):
        all_scripts = shot.get("all_script_files", {})
        if not all_scripts:
            QMessageBox.warning(self, "Missing Scripts", f"No Nuke scripts found for {shot['shot_name']}.")
            return
        for ver in shot.get("all_script_versions", sorted(all_scripts.keys())):
            path = all_scripts.get(ver)
            if path:
                self._queue_render_jobs([shot], write_node="Write_REVIEW", explicit_script_path=path, explicit_version=ver)

    def on_execute_delivery(self):
        deliv_dir_str = self.meta.get("delivery_dir")
        if not deliv_dir_str or not Path(deliv_dir_str).exists():
            QMessageBox.warning(self, "Delivery Error", "Delivery directory is not configured. Please click Settings.")
            return

        delivery_root = Path(deliv_dir_str)

        to_deliver = []
        for shot in self.scanned_shots:
            shot_key = f"{shot['seq_name']}_{shot['shot_name']}"
            info = self.shot_data.get(shot_key, {})
            if info.get("marked_for_delivery"):
                to_deliver.append({
                    "seq_name": shot["seq_name"],
                    "shot_name": shot["shot_name"],
                    "version": info.get("delivery_version", "v001"),
                    "copy_hires": True,
                    "copy_review": True
                })

        if not to_deliver:
            QMessageBox.information(self, "No Shots Marked", "No shots are marked for delivery. Check the 'Deliver' box on the shots you wish to send.")
            return

        # Check render files on disk before executing delivery
        check_results = DeliveryManager.check_delivery_files(self.project_path, to_deliver)
        missing_items = [item for item in check_results if item["missing"]]

        any_files_found = any(item["has_review"] or item["has_hires"] for item in check_results)
        if not any_files_found:
            QMessageBox.critical(
                self,
                "Missing Renders",
                "None of the selected shots have rendered review or hires files on disk for their chosen delivery versions.\n\n"
                "Please render the shots before executing client delivery."
            )
            return

        if missing_items:
            details_lines = []
            for item in missing_items:
                shot_name = item["shot_name"]
                ver = item["version"]
                missing = item["missing"]
                if "review" in missing and "hires" in missing:
                    status_desc = "Missing BOTH Hires EXR & Review MOV"
                elif "hires" in missing:
                    status_desc = "Missing Hires EXR (Review MOV found)"
                else:
                    status_desc = "Missing Review MOV (Hires EXR found)"
                details_lines.append(f"• {shot_name} ({ver}): {status_desc}")

            shots_summary = "\n".join(details_lines[:15])
            if len(details_lines) > 15:
                shots_summary += f"\n... and {len(details_lines) - 15} more shots with missing renders."

            warn_msg = (
                f"<b>Missing Renders Detected!</b><br><br>"
                f"The following {len(missing_items)} of {len(to_deliver)} selected shot(s) are missing render files for their delivery version:<br><br>"
                f"<pre style='background-color: #2b2b36; padding: 10px; border-radius: 4px; color: #ffb74d;'>{shots_summary}</pre><br>"
                f"If you continue, only the available render files will be copied to:<br>"
                f"<code>{delivery_root}</code><br><br>"
                f"Do you want to proceed anyway?"
            )

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Missing Render Warning")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setTextFormat(Qt.RichText)
            msg_box.setText(warn_msg)
            btn_deliver_anyway = msg_box.addButton("Deliver Available Files", QMessageBox.AcceptRole)
            btn_cancel = msg_box.addButton("Cancel", QMessageBox.RejectRole)
            msg_box.setDefaultButton(btn_cancel)
            msg_box.exec()

            if msg_box.clickedButton() != btn_deliver_anyway:
                return
        else:
            reply = QMessageBox.question(
                self,
                "Confirm Delivery",
                f"You are about to deliver {len(to_deliver)} shots to:\n{delivery_root}\n\n"
                f"All review and hires renders verified on disk.\n\n"
                f"Proceed with transfer?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        # Active progress loader dialog during delivery
        progress_dlg = QProgressDialog(
            "Transferring shots to client delivery folder...",
            "Cancel",
            0,
            len(to_deliver),
            self
        )
        progress_dlg.setWindowTitle("Delivering Shots to Client")
        progress_dlg.setWindowModality(Qt.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(0)
        QApplication.processEvents()

        def on_delivery_progress(cur: int, total: int, label: str):
            if progress_dlg.wasCanceled():
                return
            progress_dlg.setValue(cur)
            progress_dlg.setLabelText(f"[{cur}/{total}] {label}")
            QApplication.processEvents()

        try:
            success, msg, files = DeliveryManager.execute_delivery(
                project_dir=self.project_path,
                delivery_root=delivery_root,
                deliveries=to_deliver,
                progress_callback=on_delivery_progress
            )
        finally:
            progress_dlg.close()

        if success:
            QMessageBox.information(self, "Delivery Complete", f"{msg}\n\nDestination:\n{delivery_root}")
            check_map = {f"{c['seq_name']}_{c['shot_name']}": c for c in check_results}
            for item in to_deliver:
                k = f"{item['seq_name']}_{item['shot_name']}"
                res = check_map.get(k)
                if res and (res["has_review"] or res["has_hires"]):
                    if k in self.shot_data:
                        self.shot_data[k]["status"] = "Delivered"
                        self.shot_data[k]["last_delivered_version"] = item["version"]
            self.save_shot_data()
            self.refresh_shots()
        else:
            QMessageBox.critical(self, "Delivery Error", msg)

    def show_shot_context_menu(self, pos):
        """Displays rich right-click context menu to open DCC scenes (Nuke, 3D, After Effects, etc.)."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        item = self.table.item(row, 2)
        if not item:
            return

        shot = item.data(Qt.UserRole)
        shot_dir = Path(shot.get("shot_dir", ""))
        shot_name = shot.get("shot_name", "Shot")

        menu = QMenu(self)

        title_action = menu.addAction(f"🎬 Shot: {shot_name}")
        title_action.setEnabled(False)
        menu.addSeparator()

        scenes_found = False

        # 1. Nuke Scripts
        comp_scripts_dir = shot_dir / "comp" / "scripts"
        if comp_scripts_dir.exists():
            nk_files = sorted(list(comp_scripts_dir.glob("*.nk")), reverse=True)
            if nk_files:
                scenes_found = True
                latest_nk = nk_files[0]
                act_latest_nk = menu.addAction(f"🟢 Open Nuke ({latest_nk.name})")
                act_latest_nk.triggered.connect(lambda _, f=latest_nk: self.launch_file(f))

                if len(nk_files) > 1:
                    sub_nk = menu.addMenu("All Nuke Script Versions")
                    for nk in nk_files:
                        sub_act = sub_nk.addAction(nk.name)
                        sub_act.triggered.connect(lambda _, f=nk: self.launch_file(f))

            # After Effects Projects (.aep)
            aep_files = sorted(list(comp_scripts_dir.glob("*.aep")), reverse=True)
            if aep_files:
                scenes_found = True
                for aep in aep_files:
                    act_aep = menu.addAction(f"🟣 Open After Effects ({aep.name})")
                    act_aep.triggered.connect(lambda _, f=aep: self.launch_file(f))

        # 2. 3D DCC Scenes (Blender, Maya, Houdini, C4D)
        scenes_3d_dir = shot_dir / "3d" / "scenes"
        if scenes_3d_dir.exists():
            blend_files = sorted(list(scenes_3d_dir.glob("*.blend")), reverse=True)
            if blend_files:
                scenes_found = True
                act_bl = menu.addAction(f"🟠 Open Blender ({blend_files[0].name})")
                act_bl.triggered.connect(lambda _, f=blend_files[0]: self.launch_file(f))

            maya_files = sorted(list(scenes_3d_dir.glob("*.ma")) + list(scenes_3d_dir.glob("*.mb")), reverse=True)
            if maya_files:
                scenes_found = True
                act_my = menu.addAction(f"🔵 Open Maya ({maya_files[0].name})")
                act_my.triggered.connect(lambda _, f=maya_files[0]: self.launch_file(f))

            hip_files = sorted(list(scenes_3d_dir.glob("*.hip*")), reverse=True)
            if hip_files:
                scenes_found = True
                act_hip = menu.addAction(f"🟧 Open Houdini ({hip_files[0].name})")
                act_hip.triggered.connect(lambda _, f=hip_files[0]: self.launch_file(f))

            c4d_files = sorted(list(scenes_3d_dir.glob("*.c4d")), reverse=True)
            if c4d_files:
                scenes_found = True
                act_c4d = menu.addAction(f"🔷 Open Cinema 4D ({c4d_files[0].name})")
                act_c4d.triggered.connect(lambda _, f=c4d_files[0]: self.launch_file(f))

        # 3. Unreal Engine Project
        ue_dir = self.project_path / "unreal_projects"
        if ue_dir.exists():
            uprojects = list(ue_dir.glob("*/*.uproject"))
            if uprojects:
                scenes_found = True
                act_ue = menu.addAction(f"🎮 Open Unreal Project ({uprojects[0].name})")
                act_ue.triggered.connect(lambda _, f=uprojects[0]: self.launch_file(f))

        if not scenes_found:
            no_scenes_act = menu.addAction("(No working scene files found)")
            no_scenes_act.setEnabled(False)

        menu.addSeparator()

        # 4. Review / Render Options
        latest_ver = shot.get("latest_script_version") or "v001"
        all_vers = shot.get("all_script_versions", [])

        if shot.get("latest_review_path"):
            act_play = menu.addAction(f"▶ Play Latest Review ({shot.get('latest_review_version')})")
            act_play.triggered.connect(lambda _, s=shot: self.open_player(s))

        act_r_rev = menu.addAction(f"🚀 Render Review ({latest_ver})")
        act_r_rev.triggered.connect(lambda _, s=shot: self.render_single_shot(s, "Write_REVIEW"))

        act_r_hi = menu.addAction(f"🚀 Render Hires ({latest_ver})")
        act_r_hi.triggered.connect(lambda _, s=shot: self.render_single_shot(s, "Write_HIRES"))

        # Specific version rendering submenu if scripts exist
        if all_vers:
            ver_menu = menu.addMenu("🎯 Render Specific Script Version...")
            for v_name in all_vers:
                v_path = shot.get("all_script_files", {}).get(v_name)
                if v_path:
                    v_sub = ver_menu.addMenu(f"📄 {v_name}")
                    act_v_rev = v_sub.addAction("Render Review MOV/MP4")
                    act_v_rev.triggered.connect(
                        lambda _, s=shot, p=v_path, v=v_name: self.render_single_shot(s, "Write_REVIEW", explicit_script_path=p, explicit_version=v)
                    )
                    act_v_hi = v_sub.addAction("Render Hires EXR")
                    act_v_hi.triggered.connect(
                        lambda _, s=shot, p=v_path, v=v_name: self.render_single_shot(s, "Write_HIRES", explicit_script_path=p, explicit_version=v)
                    )

            if len(all_vers) > 1:
                act_all_v = menu.addAction(f"⚡ Render All Script Versions ({len(all_vers)} versions)")
                act_all_v.triggered.connect(lambda _, s=shot: self.render_all_versions_of_shot(s))

        menu.addSeparator()

        # 5. Explorer Folders Submenu
        folders_menu = menu.addMenu("📁 Open In Explorer")

        act_f_shot = folders_menu.addAction("Shot Root Folder")
        act_f_shot.triggered.connect(lambda _, p=shot_dir: self.open_folder(p))

        plates_dir = shot_dir / "plates"
        if plates_dir.exists():
            act_f_plates = folders_menu.addAction("Plates Folder")
            act_f_plates.triggered.connect(lambda _, p=plates_dir: self.open_folder(p))

        renders_dir = shot_dir / "renders"
        if renders_dir.exists():
            act_f_renders = folders_menu.addAction("Renders Folder")
            act_f_renders.triggered.connect(lambda _, p=renders_dir: self.open_folder(p))

        if comp_scripts_dir.exists():
            act_f_comp = folders_menu.addAction("Comp Scripts Folder")
            act_f_comp.triggered.connect(lambda _, p=comp_scripts_dir: self.open_folder(p))

        if scenes_3d_dir.exists():
            act_f_3d = folders_menu.addAction("3D Scenes Folder")
            act_f_3d.triggered.connect(lambda _, p=scenes_3d_dir: self.open_folder(p))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def launch_file(self, file_path: Path):
        """Launches a DCC scene with its configured application executable or system default."""
        if not file_path.exists():
            QMessageBox.warning(self, "File Not Found", f"File does not exist: {file_path}")
            return

        str_path = str(file_path)
        ext = file_path.suffix.lower()
        dcc_paths = get_dcc_paths()

        exe_path = ""
        if ext == ".nk":
            exe_path = dcc_paths.get("nuke") or find_nuke_executable() or ""
        elif ext in [".ma", ".mb"]:
            exe_path = dcc_paths.get("maya", "")
        elif ext == ".blend":
            exe_path = dcc_paths.get("blender", "")
        elif ext == ".aep":
            exe_path = dcc_paths.get("after_effects", "")
        elif ext in [".hip", ".hiplc", ".hipnc"]:
            exe_path = dcc_paths.get("houdini", "")
        elif ext == ".uproject":
            exe_path = dcc_paths.get("unreal", "")

        if exe_path and Path(exe_path).exists():
            try:
                subprocess.Popen([exe_path, str_path])
                return
            except Exception as e:
                print(f"Warning: Direct launch with {exe_path} failed: {e}")

        # Fallback to system OS file associations
        try:
            if sys.platform == "win32":
                os.startfile(str_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str_path])
            else:
                subprocess.Popen(["xdg-open", str_path])
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Failed to open {file_path.name}:\n{e}")

    def open_folder(self, folder_path: Path):
        """Opens folder in system explorer."""
        if folder_path.exists():
            if sys.platform == "win32":
                os.startfile(str(folder_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder_path)])
            else:
                subprocess.run(["xdg-open", str(folder_path)])

    def open_selected_shot_folder(self):
        curr_row = self.table.currentRow()
        if curr_row < 0:
            return
        item = self.table.item(curr_row, 2)
        if not item:
            return
        shot = item.data(Qt.UserRole)
        p = shot.get("shot_dir")
        if p and Path(p).exists():
            if sys.platform == "win32":
                os.startfile(p)
            else:
                subprocess.run(["xdg-open", p])

    def open_delivery_folder(self):
        deliv_dir = self.meta.get("delivery_dir")
        if deliv_dir and Path(deliv_dir).exists():
            if sys.platform == "win32":
                os.startfile(deliv_dir)
            else:
                subprocess.run(["xdg-open", deliv_dir])
        else:
            QMessageBox.information(self, "Delivery", "Delivery directory is not configured yet.")
