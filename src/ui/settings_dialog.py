"""
Settings and About Dialog for Post Project Manager.
Contains General About info and the Pipeline Manual (Template JSON Editor).
"""

import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget
)

from ..core.pipeline import PipelineManager
from ..version import __app_name__, __author__, __version__


class SettingsDialog(QDialog):
    def __init__(self, pipeline_manager: PipelineManager, parent=None):
        super().__init__(parent)
        self.pm = pipeline_manager

        self.setWindowTitle("Settings & About")
        self.resize(750, 580)

        self.init_ui()
        self.load_template_content()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        self.tabs = QTabWidget()

        # Tab 1: About
        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        about_layout.setSpacing(16)
        about_layout.setContentsMargins(20, 20, 20, 20)

        card = QGroupBox("Application Information")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(18, 18, 18, 18)

        app_title = QLabel(f"<b style='font-size: 20px; color: #4da6ff;'>{__app_name__}</b>")
        card_layout.addWidget(app_title)

        app_desc = QLabel(
            "Modular Project Scaffolding & Pipeline Manager for Post-Production.<br>"
            "Designed for VFX, 3D DCC, Unreal Engine, Compositing and AI workflows."
        )
        app_desc.setStyleSheet("color: #b0b0b8; font-size: 12px;")
        card_layout.addWidget(app_desc)

        card_layout.addSpacing(6)

        info_grid = QVBoxLayout()
        info_grid.setSpacing(8)

        lbl_version = QLabel(f"<b>Version:</b> <span style='color: #81c784;'>v{__version__}</span>")
        lbl_version.setStyleSheet("font-size: 13px;")
        info_grid.addWidget(lbl_version)

        lbl_author = QLabel(f"<b>Author:</b> <span style='color: #ffffff;'>{__author__}</span>")
        lbl_author.setStyleSheet("font-size: 13px;")
        info_grid.addWidget(lbl_author)

        lbl_email = QLabel("<b>Email:</b> <a href='mailto:cristianfieiras@gmail.com' style='color: #4da6ff;'>cristianfieiras@gmail.com</a>")
        lbl_email.setOpenExternalLinks(True)
        lbl_email.setStyleSheet("font-size: 13px;")
        info_grid.addWidget(lbl_email)

        lbl_github = QLabel("<b>GitHub:</b> <a href='https://github.com/cfieiras/post-project-manager' style='color: #4da6ff;'>github.com/cfieiras/post-project-manager</a>")
        lbl_github.setOpenExternalLinks(True)
        lbl_github.setStyleSheet("font-size: 13px;")
        info_grid.addWidget(lbl_github)

        card_layout.addLayout(info_grid)
        about_layout.addWidget(card)
        about_layout.addStretch()

        self.tabs.addTab(about_tab, "About")

        # Tab 2: Folder Structure Editor (Template Editor)
        manual_tab = QWidget()
        manual_layout = QVBoxLayout(manual_tab)
        manual_layout.setSpacing(10)
        manual_layout.setContentsMargins(14, 14, 14, 14)

        info_manual = QLabel(
            "<b>Folder Structure Schema (pipeline_template.json)</b><br>"
            "Customize the default studio folder hierarchy, core directories, and module configurations.<br>"
            "Changes will automatically apply to newly created projects."
        )
        info_manual.setStyleSheet("color: #b0b0b8; font-size: 11px;")
        manual_layout.addWidget(info_manual)

        self.editor = QTextEdit()
        self.editor.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 12px; background-color: #141416;"
        )
        self.editor.textChanged.connect(self.validate_json)
        manual_layout.addWidget(self.editor)

        self.status_label = QLabel("✔ JSON syntax is valid.")
        self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        manual_layout.addWidget(self.status_label)

        manual_btn_bar = QHBoxLayout()
        btn_reset = QPushButton("Reset to Factory Default")
        btn_reset.clicked.connect(self.on_reset_default)
        manual_btn_bar.addWidget(btn_reset)

        manual_btn_bar.addStretch()

        self.btn_save_manual = QPushButton("Save Folder Structure")
        self.btn_save_manual.setObjectName("primaryButton")
        self.btn_save_manual.clicked.connect(self.on_save_manual)
        manual_btn_bar.addWidget(self.btn_save_manual)

        manual_layout.addLayout(manual_btn_bar)

        self.tabs.addTab(manual_tab, "Folder Structure Editor")

        main_layout.addWidget(self.tabs)

        # Bottom Close Button
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        bottom_bar.addWidget(btn_close)
        main_layout.addLayout(bottom_bar)

    def load_template_content(self):
        text = json.dumps(self.pm.template, indent=2, ensure_ascii=False)
        self.editor.setPlainText(text)

    def validate_json(self):
        try:
            json.loads(self.editor.toPlainText())
            self.status_label.setText("✔ JSON syntax is valid.")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
            self.btn_save_manual.setEnabled(True)
        except Exception as e:
            self.status_label.setText(f"✘ Syntax Error: {e}")
            self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;")
            self.btn_save_manual.setEnabled(False)

    def on_reset_default(self):
        reply = QMessageBox.question(
            self,
            "Reset Confirmation",
            "Are you sure you want to restore the factory default directory schema?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            fallback = self.pm._get_fallback_template()
            self.editor.setPlainText(json.dumps(fallback, indent=2, ensure_ascii=False))

    def on_save_manual(self):
        try:
            data = json.loads(self.editor.toPlainText())
            if self.pm.save_template(data):
                QMessageBox.information(self, "Success", "Folder structure template successfully updated!")
            else:
                QMessageBox.critical(self, "Error", "Failed to write template file to disk.")
        except Exception as e:
            QMessageBox.critical(self, "Validation Error", f"Cannot save invalid JSON: {e}")
