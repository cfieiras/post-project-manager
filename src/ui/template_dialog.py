"""
Template and Manual Editor Dialog for Post Project Manager.
Allows studio leads to customize folder naming conventions and modules in JSON.
"""

import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QMessageBox
)

from ..core.pipeline import PipelineManager


class TemplateDialog(QDialog):
    def __init__(self, pipeline_manager: PipelineManager, parent=None):
        super().__init__(parent)
        self.pm = pipeline_manager
        self.setWindowTitle("Pipeline Architecture Manual (Template JSON Editor)")
        self.resize(750, 600)

        self.init_ui()
        self.load_current_template()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        info_label = QLabel(
            "<b>Specification Schema (pipeline_template.json)</b><br>"
            "Modify the studio standard structure, core directories, or module configurations.<br>"
            "Changes will apply to all newly created projects."
        )
        info_label.setStyleSheet("color: #b0b0b8; font-size: 11px;")
        layout.addWidget(info_label)

        self.editor = QTextEdit()
        self.editor.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 12px; background-color: #161618;")
        self.editor.textChanged.connect(self.validate_json)
        layout.addWidget(self.editor)

        self.status_label = QLabel("JSON Valid")
        self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_reset = QPushButton("Reset to Factory Default")
        btn_reset.clicked.connect(self.on_reset_default)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        self.btn_save = QPushButton("Save Manual")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self.on_save)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def load_current_template(self):
        text = json.dumps(self.pm.template, indent=2, ensure_ascii=False)
        self.editor.setPlainText(text)

    def validate_json(self):
        try:
            json.loads(self.editor.toPlainText())
            self.status_label.setText("✔ JSON syntax is valid.")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
            self.btn_save.setEnabled(True)
        except Exception as e:
            self.status_label.setText(f"✘ Syntax Error: {e}")
            self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;")
            self.btn_save.setEnabled(False)

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

    def on_save(self):
        try:
            data = json.loads(self.editor.toPlainText())
            if self.pm.save_template(data):
                QMessageBox.information(self, "Success", "Template manual successfully updated!")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to write template file to disk.")
        except Exception as e:
            QMessageBox.critical(self, "Validation Error", f"Cannot save invalid JSON: {e}")
