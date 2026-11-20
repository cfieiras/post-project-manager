"""
Studio Project Manager Window (ShotGrid-Lite).
Central production hub for tracking shot statuses, version synchronization,
in-app video reviews, headless batch rendering, and structured client deliveries.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMenu, QMessageBox, QPushButton, QStatusBar, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from ..core.delivery_manager import DeliveryManager
from ..core.nuke_runner import find_nuke_executable
from ..core.shot_scanner import ShotScanner
from .batch_render_dialog import BatchRenderDialog
from .delivery_setup_dialog import DeliverySetupDialog
from .player_dialog import ReviewPlayerDialog


STATUS_COLORS = {
    "Not Started": "#757575",
    "In Progress": "#0288d1",
    "Pending Review": "#f57c00",
    "Approved": "#388e3c",
    "Delivered": "#7b1fa2",
    "On Hold": "#d32f2f"
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

        self.setWindowTitle(f"Project Manager - {self.project_path.name}")
        self.resize(1280, 750)
        self.setMinimumSize(1000, 600)

        self.init_ui()
        self.refresh_shots()

        # Check delivery folder setup after window is displayed
        QTimer.singleShot(150, self.check_initial_delivery_setup)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # 1. Top Metadata & Sequence Filter Bar
        top_bar = QHBoxLayout()

        # Project Info
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

        # Sequence Filter
        top_bar.addWidget(QLabel("<b>Filter Sequence:</b>"))
        self.seq_filter_combo = QComboBox()
        self.seq_filter_combo.addItem("All Sequences")
        for seq_name in self.meta.get("sequences", {}).keys():
            self.seq_filter_combo.addItem(seq_name)
        self.seq_filter_combo.currentTextChanged.connect(self.apply_filter)
        top_bar.addWidget(self.seq_filter_combo)

        # Delivery settings button
        self.btn_delivery_settings = QPushButton("⚙ Delivery Settings")
        self.btn_delivery_settings.clicked.connect(self.open_delivery_setup)
        top_bar.addWidget(self.btn_delivery_settings)

        btn_refresh = QPushButton("↻ Refresh Disk")
        btn_refresh.clicked.connect(self.refresh_shots)
        top_bar.addWidget(btn_refresh)

        main_layout.addLayout(top_bar)

        # Delivery path indicator badge
        self.delivery_lbl = QLabel("Delivery Folder: Not Configured")
        self.delivery_lbl.setStyleSheet("color: #b0b0b8; font-size: 11px;")
        self.update_delivery_label()
        main_layout.addWidget(self.delivery_lbl)

        # 2. Main ShotGrid-Lite Table
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Select", "Thumbnail", "Shot ID", "Status", "Notes & Supervisor Feedback",
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
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(9, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_shot_context_menu)
        main_layout.addWidget(self.table)

        # 3. Bottom Action Bar
        bottom_bar = QHBoxLayout()

        btn_batch_render = QPushButton("🚀 Batch Render Selected")
        btn_batch_render.setObjectName("primaryButton")
        btn_batch_render.clicked.connect(self.on_batch_render)
        bottom_bar.addWidget(btn_batch_render)

        btn_deliver = QPushButton("📦 Execute Client Delivery")
        btn_deliver.clicked.connect(self.on_execute_delivery)
        bottom_bar.addWidget(btn_deliver)

        bottom_bar.addSpacing(20)

        btn_open_shot = QPushButton("📁 Open Shot Folder")
        btn_open_shot.clicked.connect(self.open_selected_shot_folder)
        bottom_bar.addWidget(btn_open_shot)

        btn_open_delivery = QPushButton("📁 Open Delivery Folder")
        btn_open_delivery.clicked.connect(self.open_delivery_folder)
        bottom_bar.addWidget(btn_open_delivery)

        bottom_bar.addStretch()

        main_layout.addLayout(bottom_bar)

        # 4. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

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
            self.delivery_lbl.setText(f"📁 <b>Delivery Folder:</b> <span style='color: #4caf50;'>{deliv}</span>")
        else:
            self.delivery_lbl.setText("📁 <b>Delivery Folder:</b> <span style='color: #ff9800;'>Not Configured (Click Delivery Settings to setup)</span>")

    def check_initial_delivery_setup(self):
        deliv = self.meta.get("delivery_dir")
        if not deliv or not Path(deliv).exists():
            # Prompt user to setup delivery folder
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

    def open_delivery_setup(self):
        dialog = DeliverySetupDialog(
            current_path=self.meta.get("delivery_dir"),
            sequences=self.meta.get("sequences", {}),
            parent=self,
            is_first_time=False
        )
        if dialog.exec() == QDialog.Accepted and dialog.selected_path:
            self.meta["delivery_dir"] = dialog.selected_path
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(self.meta, f, indent=2, ensure_ascii=False)
            self.update_delivery_label()

    def refresh_shots(self):
        sequences = self.meta.get("sequences", {})
        self.scanned_shots = ShotScanner.scan_all_shots(self.project_path, sequences)
        self.apply_filter()

    def apply_filter(self):
        selected_seq = self.seq_filter_combo.currentText()
        filtered = [
            s for s in self.scanned_shots
            if selected_seq == "All Sequences" or s["seq_name"] == selected_seq
        ]

        self.table.setRowCount(len(filtered))
        for row, shot in enumerate(filtered):
            shot_key = f"{shot['seq_name']}_{shot['shot_name']}"
            saved_info = self.shot_data.get(shot_key, {})

            # 0. Selection Checkbox
            cb_item = QCheckBox()
            cb_item.setStyleSheet("margin-left: 8px;")
            self.table.setCellWidget(row, 0, cb_item)

            # 1. Thumbnail / Play Button
            btn_thumb = QPushButton("▶ Play" if shot.get("latest_review_path") else "No Video")
            btn_thumb.setEnabled(bool(shot.get("latest_review_path")))
            if shot.get("latest_review_path"):
                btn_thumb.clicked.connect(lambda _, s=shot: self.open_player(s))
            self.table.setCellWidget(row, 1, btn_thumb)

            # 2. Shot ID
            item_shot = QTableWidgetItem(shot["shot_name"])
            item_shot.setData(Qt.UserRole, shot)
            item_shot.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item_shot)

            # 3. Status Dropdown
            status_combo = QComboBox()
            for st, col in STATUS_COLORS.items():
                status_combo.addItem(st)

            current_status = saved_info.get("status", "Not Started")
            idx = status_combo.findText(current_status)
            if idx >= 0:
                status_combo.setCurrentIndex(idx)
            self.apply_combo_color(status_combo, current_status)
            status_combo.currentTextChanged.connect(
                lambda val, k=shot_key, sc=status_combo: self.on_status_changed(k, val, sc)
            )
            self.table.setCellWidget(row, 3, status_combo)

            # 4. Notes LineEdit
            notes_edit = QLineEdit(saved_info.get("notes", ""))
            notes_edit.setPlaceholderText("Add notes...")
            notes_edit.editingFinished.connect(
                lambda k=shot_key, ne=notes_edit: self.on_notes_changed(k, ne.text())
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

            # 8. Render Action Buttons
            render_widget = QWidget()
            rw_layout = QHBoxLayout(render_widget)
            rw_layout.setContentsMargins(2, 2, 2, 2)
            rw_layout.setSpacing(4)

            btn_r_rev = QPushButton("Review")
            btn_r_rev.setToolTip("Render Review MOV/MP4")
            btn_r_rev.clicked.connect(lambda _, s=shot: self.render_single_shot(s, "Write_REVIEW"))
            rw_layout.addWidget(btn_r_rev)

            btn_r_hires = QPushButton("Hires")
            btn_r_hires.setToolTip("Render Hires EXR")
            btn_r_hires.clicked.connect(lambda _, s=shot: self.render_single_shot(s, "Write_HIRES"))
            rw_layout.addWidget(btn_r_hires)
            self.table.setCellWidget(row, 8, render_widget)

            # 9. Delivery Version Combo & Check
            deliv_widget = QWidget()
            dw_layout = QHBoxLayout(deliv_widget)
            dw_layout.setContentsMargins(4, 2, 4, 2)
            dw_layout.setSpacing(6)

            cb_deliver = QCheckBox("Deliver")
            cb_deliver.setChecked(saved_info.get("marked_for_delivery", False))

            combo_deliv_ver = QComboBox()
            # Combine available versions
            all_vers = sorted(list(set(
                list(shot.get("all_review_versions", {}).keys()) +
                shot.get("all_hires_versions", [])
            )), reverse=True)
            if not all_vers:
                all_vers = ["v001"]
            for v in all_vers:
                combo_deliv_ver.addItem(v)

            saved_ver = saved_info.get("delivery_version")
            if saved_ver and saved_ver in all_vers:
                combo_deliv_ver.setCurrentText(saved_ver)

            cb_deliver.stateChanged.connect(
                lambda state, k=shot_key, cv=combo_deliv_ver: self.on_delivery_toggled(k, state, cv.currentText())
            )
            combo_deliv_ver.currentTextChanged.connect(
                lambda val, k=shot_key, cb=cb_deliver: self.on_delivery_toggled(k, cb.isChecked(), val)
            )

            dw_layout.addWidget(cb_deliver)
            dw_layout.addWidget(combo_deliv_ver)
            self.table.setCellWidget(row, 9, deliv_widget)

        self.status_bar.showMessage(f"Loaded {len(filtered)} shots.")

    def apply_combo_color(self, combo: QComboBox, status: str):
        col = STATUS_COLORS.get(status, "#757575")
        combo.setStyleSheet(f"color: {col}; font-weight: bold;")

    def on_status_changed(self, shot_key: str, status: str, combo: QComboBox):
        self.apply_combo_color(combo, status)
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

        dialog = ReviewPlayerDialog(
            shot_name=shot["shot_name"],
            review_versions=rev_dict,
            initial_version=latest_v,
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

    def on_batch_render(self):
        selected = self.get_selected_shots()
        if not selected:
            QMessageBox.information(self, "Selection Required", "Please select at least one shot via the checkbox.")
            return

        dialog = BatchRenderDialog(selected, parent=self)
        dialog.exec()
        self.refresh_shots()

    def render_single_shot(self, shot: Dict[str, Any], write_node: str):
        if not shot.get("latest_script_path"):
            QMessageBox.warning(self, "Missing Script", f"No Nuke script found for {shot['shot_name']}.")
            return

        dialog = BatchRenderDialog([shot], parent=self)
        if write_node == "Write_REVIEW":
            dialog.rb_review.setChecked(True)
        else:
            dialog.rb_hires.setChecked(True)
        dialog.start_rendering()
        dialog.exec()
        self.refresh_shots()

    def on_execute_delivery(self):
        deliv_dir_str = self.meta.get("delivery_dir")
        if not deliv_dir_str or not Path(deliv_dir_str).exists():
            QMessageBox.warning(self, "Delivery Error", "Delivery directory is not configured. Please click Delivery Settings.")
            return

        delivery_root = Path(deliv_dir_str)

        # Collect all shots marked for delivery
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

        reply = QMessageBox.question(
            self,
            "Confirm Delivery",
            f"You are about to deliver {len(to_deliver)} shots to:\n{delivery_root}\n\nProceed with transfer?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        success, msg, files = DeliveryManager.execute_delivery(
            project_dir=self.project_path,
            delivery_root=delivery_root,
            deliveries=to_deliver
        )

        if success:
            QMessageBox.information(self, "Delivery Complete", f"{msg}\n\nDestination:\n{delivery_root}")
            # Update status to Delivered
            for item in to_deliver:
                k = f"{item['seq_name']}_{item['shot_name']}"
                if k in self.shot_data:
                    self.shot_data[k]["status"] = "Delivered"
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

        # Header Title
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
            # Blender
            blend_files = sorted(list(scenes_3d_dir.glob("*.blend")), reverse=True)
            if blend_files:
                scenes_found = True
                act_bl = menu.addAction(f"🟠 Open Blender ({blend_files[0].name})")
                act_bl.triggered.connect(lambda _, f=blend_files[0]: self.launch_file(f))

            # Maya
            maya_files = sorted(list(scenes_3d_dir.glob("*.ma")) + list(scenes_3d_dir.glob("*.mb")), reverse=True)
            if maya_files:
                scenes_found = True
                act_my = menu.addAction(f"🔵 Open Maya ({maya_files[0].name})")
                act_my.triggered.connect(lambda _, f=maya_files[0]: self.launch_file(f))

            # Houdini
            hip_files = sorted(list(scenes_3d_dir.glob("*.hip*")), reverse=True)
            if hip_files:
                scenes_found = True
                act_hip = menu.addAction(f"🟧 Open Houdini ({hip_files[0].name})")
                act_hip.triggered.connect(lambda _, f=hip_files[0]: self.launch_file(f))

            # Cinema 4D
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
        if shot.get("latest_review_path"):
            act_play = menu.addAction(f"▶ Play Latest Review ({shot.get('latest_review_version')})")
            act_play.triggered.connect(lambda _, s=shot: self.open_player(s))

        act_r_rev = menu.addAction("🚀 Render Review MOV (Nuke)")
        act_r_rev.triggered.connect(lambda _, s=shot: self.render_single_shot(s, "Write_REVIEW"))

        act_r_hi = menu.addAction("🚀 Render Hires EXR (Nuke)")
        act_r_hi.triggered.connect(lambda _, s=shot: self.render_single_shot(s, "Write_HIRES"))

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
        """Launches a DCC scene with its associated software or detected executable."""
        if not file_path.exists():
            QMessageBox.warning(self, "File Not Found", f"File does not exist: {file_path}")
            return

        str_path = str(file_path)

        # For Nuke scripts (.nk), prefer detected Nuke executable if available
        if file_path.suffix.lower() == ".nk":
            nuke_exe = find_nuke_executable()
            if nuke_exe and Path(nuke_exe).exists():
                try:
                    subprocess.Popen([nuke_exe, str_path])
                    return
                except Exception as e:
                    print(f"Warning: Direct Nuke launch failed: {e}")

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
