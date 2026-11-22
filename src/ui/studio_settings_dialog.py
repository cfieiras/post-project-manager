"""
Studio & Project Settings Dialog.
Configures Client Delivery directories (with progress loader) and DCC application executable paths.
"""

import glob
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QTabWidget, QVBoxLayout, QWidget
)

from ..core.config_manager import get_dcc_paths, save_dcc_paths
from ..core.delivery_manager import DeliveryManager
from ..core.nuke_runner import find_nuke_executable
from .theme import get_app_icon


def auto_detect_dcc_paths() -> Dict[str, str]:
    """Scans standard installation locations for DCC executables."""
    detected = {
        "nuke": find_nuke_executable() or "",
        "maya": "",
        "blender": "",
        "after_effects": "",
        "houdini": "",
        "unreal": ""
    }

    if sys.platform == "win32":
        # Maya
        for m in sorted(glob.glob(r"C:\Program Files\Autodesk\Maya*\bin\maya.exe"), reverse=True):
            if Path(m).exists():
                detected["maya"] = m
                break

        # Blender
        for b in sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"), reverse=True):
            if Path(b).exists():
                detected["blender"] = b
                break

        # After Effects
        for ae in sorted(glob.glob(r"C:\Program Files\Adobe\Adobe After Effects*\Support Files\AfterFX.exe"), reverse=True):
            if Path(ae).exists():
                detected["after_effects"] = ae
                break

        # Houdini
        for h in sorted(glob.glob(r"C:\Program Files\Side Effects Software\Houdini*\bin\hindie.exe") +
                        glob.glob(r"C:\Program Files\Side Effects Software\Houdini*\bin\houdini.exe"), reverse=True):
            if Path(h).exists():
                detected["houdini"] = h
                break

        # Unreal
        for ue in sorted(glob.glob(r"C:\Program Files\Epic Games\UE_*\Engine\Binaries\Win64\UnrealEditor.exe"), reverse=True):
            if Path(ue).exists():
                detected["unreal"] = ue
                break

    return detected


class StudioSettingsDialog(QDialog):
    def __init__(
        self,
        current_delivery_path: Optional[str] = None,
        sequences: Optional[Dict[str, List[str]]] = None,
        project_settings: Optional[Dict[str, Any]] = None,
        parent=None,
        active_tab: int = 0
    ):
        super().__init__(parent)
        self.sequences = sequences or {}
        self.project_settings = dict(project_settings or {})
        self.updated_project_settings: Optional[Dict[str, Any]] = None
        self.selected_delivery_path: Optional[str] = None
        self.dcc_inputs: Dict[str, QLineEdit] = {}

        self.setWindowTitle("Settings - Studio & Project Configuration")
        self.setWindowIcon(get_app_icon())
        self.resize(750, 520)
        self.setMinimumSize(660, 440)

        self.init_ui(current_delivery_path, active_tab)

    def init_ui(self, current_delivery_path: Optional[str], active_tab: int):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        self.tabs = QTabWidget()

        # ================= TAB 1: CLIENT DELIVERY =================
        tab_delivery = QWidget()
        deliv_layout = QVBoxLayout(tab_delivery)
        deliv_layout.setContentsMargins(14, 14, 14, 14)
        deliv_layout.setSpacing(12)

        deliv_info = QLabel(
            "<b style='color: #4da6ff; font-size: 14px;'>Client Delivery Folder</b><br>"
            "Specify the external folder used for client deliveries (e.g. Google Drive, Dropbox, Server).<br>"
            "When confirmed, all project sequences and shots will be automatically verified and scaffolded."
        )
        deliv_info.setWordWrap(True)
        deliv_layout.addWidget(deliv_info)

        deliv_group = QGroupBox("Delivery Directory Destination")
        deliv_group_layout = QHBoxLayout(deliv_group)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select external delivery directory...")
        if current_delivery_path:
            self.path_edit.setText(current_delivery_path)
        deliv_group_layout.addWidget(self.path_edit)

        btn_browse_deliv = QPushButton("Browse...")
        btn_browse_deliv.clicked.connect(self.browse_delivery_folder)
        deliv_group_layout.addWidget(btn_browse_deliv)

        deliv_layout.addWidget(deliv_group)

        # Loader Bar & Status Text
        self.deliv_status_lbl = QLabel("")
        self.deliv_status_lbl.setStyleSheet("color: #4da6ff; font-weight: bold; font-size: 11px;")
        self.deliv_status_lbl.setVisible(False)
        deliv_layout.addWidget(self.deliv_status_lbl)

        self.deliv_loader_bar = QProgressBar()
        self.deliv_loader_bar.setRange(0, 0)
        self.deliv_loader_bar.setTextVisible(False)
        self.deliv_loader_bar.setFixedHeight(6)
        self.deliv_loader_bar.setVisible(False)
        deliv_layout.addWidget(self.deliv_loader_bar)

        deliv_layout.addStretch()

        deliv_btn_bar = QHBoxLayout()
        deliv_btn_bar.addStretch()
        self.btn_confirm_deliv = QPushButton("Confirm")
        self.btn_confirm_deliv.setObjectName("primaryButton")
        self.btn_confirm_deliv.clicked.connect(self.on_confirm_delivery)
        deliv_btn_bar.addWidget(self.btn_confirm_deliv)
        deliv_layout.addLayout(deliv_btn_bar)

        self.tabs.addTab(tab_delivery, "Client Delivery")

        # ================= TAB 2: DCC EXECUTABLES =================
        tab_dcc = QWidget()
        dcc_layout = QVBoxLayout(tab_dcc)
        dcc_layout.setContentsMargins(14, 14, 14, 14)
        dcc_layout.setSpacing(12)

        dcc_info = QLabel(
            "<b style='color: #4da6ff; font-size: 14px;'>DCC Application Executables</b><br>"
            "Configure executable paths for Nuke, 3D DCCs, After Effects, and Unreal Engine.<br>"
            "Right-clicking on any shot in the Project Manager will directly launch the working scene with the configured software."
        )
        dcc_info.setWordWrap(True)
        dcc_layout.addWidget(dcc_info)

        dcc_group = QGroupBox("Configured Software Executables")
        dcc_form = QFormLayout(dcc_group)
        dcc_form.setSpacing(8)

        configured_paths = get_dcc_paths()

        dcc_definitions = [
            ("nuke", "Nuke Executable:", "*.exe"),
            ("maya", "Maya Executable:", "*.exe"),
            ("blender", "Blender Executable:", "*.exe"),
            ("after_effects", "After Effects Executable:", "*.exe"),
            ("houdini", "Houdini Executable:", "*.exe"),
            ("unreal", "Unreal Engine Editor:", "*.exe")
        ]

        for key, label, filter_pat in dcc_definitions:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"Path to {label.replace(':', '')} binary...")
            line_edit.setText(configured_paths.get(key, ""))
            row_layout.addWidget(line_edit)

            btn_browse = QPushButton("Browse...")
            btn_browse.clicked.connect(lambda _, le=line_edit, name=label: self.browse_dcc(le, name))
            row_layout.addWidget(btn_browse)

            self.dcc_inputs[key] = line_edit
            dcc_form.addRow(label, row_widget)

        dcc_layout.addWidget(dcc_group)

        dcc_btn_bar = QHBoxLayout()
        btn_autodetect = QPushButton("🔍 Auto-Detect Installed DCCs")
        btn_autodetect.clicked.connect(self.on_autodetect_dcc)
        dcc_btn_bar.addWidget(btn_autodetect)

        dcc_btn_bar.addStretch()

        btn_save_dcc = QPushButton("Save Executable Paths")
        btn_save_dcc.setObjectName("primaryButton")
        btn_save_dcc.clicked.connect(self.on_save_dcc_paths)
        dcc_btn_bar.addWidget(btn_save_dcc)

        dcc_layout.addLayout(dcc_btn_bar)
        self.tabs.addTab(tab_dcc, "DCC Applications")

        # ================= TAB 3: REVIEW RENDER SPECS =================
        tab_review = QWidget()
        review_layout = QVBoxLayout(tab_review)
        review_layout.setContentsMargins(14, 14, 14, 14)
        review_layout.setSpacing(12)

        rev_info = QLabel(
            "<b style='color: #4da6ff; font-size: 14px;'>Nuke Review Render Specifications</b><br>"
            "Configure the default resolution and video compression codec used when rendering daily reviews."
        )
        rev_info.setWordWrap(True)
        review_layout.addWidget(rev_info)

        rev_group = QGroupBox("Review Render Output Settings")
        rev_form = QFormLayout(rev_group)
        rev_form.setSpacing(10)

        self.review_res_combo = QComboBox()
        self.review_res_combo.addItems([
            "Same as Project (100%)",
            "1920x1080 (HD_1080)",
            "1280x720 (720p HD)",
            "960x540 (Half HD - 540p)"
        ])
        saved_res = self.project_settings.get("review_resolution", "Same as Project (100%)")
        idx_res = self.review_res_combo.findText(saved_res)
        if idx_res >= 0:
            self.review_res_combo.setCurrentIndex(idx_res)
        rev_form.addRow("Review Resolution:", self.review_res_combo)

        self.review_format_combo = QComboBox()
        self.review_format_combo.addItems([
            "MOV - Apple ProRes 422",
            "MOV - Apple ProRes 422 Proxy",
            "MP4 - H.264",
            "MOV - H.264"
        ])
        saved_codec = self.project_settings.get("review_codec", "Apple ProRes 422")
        for i in range(self.review_format_combo.count()):
            if saved_codec.lower() in self.review_format_combo.itemText(i).lower():
                self.review_format_combo.setCurrentIndex(i)
                break
        rev_form.addRow("Review Format & Codec:", self.review_format_combo)

        review_layout.addWidget(rev_group)
        review_layout.addStretch()

        rev_btn_bar = QHBoxLayout()
        rev_btn_bar.addStretch()
        btn_save_rev = QPushButton("Save Review Settings")
        btn_save_rev.setObjectName("primaryButton")
        btn_save_rev.clicked.connect(self.on_save_review_settings)
        rev_btn_bar.addWidget(btn_save_rev)
        review_layout.addLayout(rev_btn_bar)

        self.tabs.addTab(tab_review, "Review Render Specs")

        self.tabs.setCurrentIndex(active_tab)
        main_layout.addWidget(self.tabs)

        # Bottom Close Button
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        bottom_bar.addWidget(btn_close)
        main_layout.addLayout(bottom_bar)

    def browse_delivery_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Client Delivery Root Directory", self.path_edit.text()
        )
        if folder:
            self.path_edit.setText(folder)

    def browse_dcc(self, line_edit: QLineEdit, name: str):
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Select {name}", line_edit.text(), "Executables (*.exe *.app *);;All Files (*)"
        )
        if file_path:
            line_edit.setText(file_path)

    def on_autodetect_dcc(self):
        detected = auto_detect_dcc_paths()
        found_any = False
        for key, path in detected.items():
            if path and key in self.dcc_inputs:
                self.dcc_inputs[key].setText(path)
                found_any = True

        if found_any:
            QMessageBox.information(
                self, "Auto-Detection Complete",
                "Installed DCC applications were successfully detected!\nClick 'Save Executable Paths' to persist."
            )
        else:
            QMessageBox.information(
                self, "Auto-Detection",
                "No DCC executables were detected in default installation directories. Please browse manually."
            )

    def on_save_dcc_paths(self):
        paths = {k: le.text().strip() for k, le in self.dcc_inputs.items()}
        if save_dcc_paths(paths):
            QMessageBox.information(self, "Success", "DCC executable paths saved successfully!")
        else:
            QMessageBox.critical(self, "Error", "Failed to save executable paths to config.json.")

    def on_save_review_settings(self):
        rev_choice = self.review_format_combo.currentText()
        if "MP4" in rev_choice:
            fmt, codec = "mp4", "H.264"
        elif "Proxy" in rev_choice:
            fmt, codec = "mov", "Apple ProRes 422 Proxy"
        elif "H.264" in rev_choice:
            fmt, codec = "mov", "H.264"
        else:
            fmt, codec = "mov", "Apple ProRes 422"

        self.project_settings["review_resolution"] = self.review_res_combo.currentText()
        self.project_settings["review_format"] = fmt
        self.project_settings["review_codec"] = codec
        self.updated_project_settings = dict(self.project_settings)

        QMessageBox.information(
            self, "Settings Updated",
            f"Review render settings saved:\n- Resolution: {self.project_settings['review_resolution']}\n- Format: {fmt.upper()} ({codec})"
        )

    def on_confirm_delivery(self):
        target = self.path_edit.text().strip()
        if not target:
            QMessageBox.warning(self, "Invalid Path", "Please specify a target delivery folder.")
            return

        target_path = Path(target)

        # Loader feedback
        self.btn_confirm_deliv.setEnabled(False)
        self.deliv_status_lbl.setText("⏳ Scaffolding delivery directory structure for all sequences & shots...")
        self.deliv_status_lbl.setVisible(True)
        self.deliv_loader_bar.setVisible(True)
        QApplication.processEvents()

        try:
            success, msg = DeliveryManager.setup_delivery_folder(target_path, self.sequences)
        finally:
            self.deliv_loader_bar.setVisible(False)
            self.deliv_status_lbl.setVisible(False)
            self.btn_confirm_deliv.setEnabled(True)

        if success:
            QMessageBox.information(self, "Delivery Scaffolded", msg)
            self.selected_delivery_path = str(target_path)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", msg)
