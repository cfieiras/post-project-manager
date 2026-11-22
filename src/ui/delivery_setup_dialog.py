"""
Delivery Setup Dialog.
Prompts user to select/initialize the external delivery folder and scaffolds all sequence/shot directories.
"""

from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QGroupBox, QProgressBar
)

from ..core.delivery_manager import DeliveryManager
from .theme import get_app_icon


class DeliverySetupDialog(QDialog):
    def __init__(
        self,
        current_path: Optional[str],
        sequences: Dict[str, List[str]],
        parent=None,
        is_first_time: bool = False
    ):
        super().__init__(parent)
        self.sequences = sequences
        self.is_first_time = is_first_time
        self.selected_path: Optional[str] = None

        self.setWindowTitle("Delivery Directory Setup" if not is_first_time else "Initialize Delivery Directory")
        self.setWindowIcon(get_app_icon())
        self.resize(650, 260)

        self.init_ui(current_path)

    def init_ui(self, current_path: Optional[str]):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header description
        if self.is_first_time:
            info_text = (
                "<b style='color: #4da6ff; font-size: 14px;'>Client Delivery Folder Not Configured</b><br>"
                "To manage client deliveries, select a delivery destination (e.g., your local Google Drive, Dropbox, or Server sync folder).<br>"
                "<b>All project sequences and shots will be automatically scaffolded inside it.</b>"
            )
        else:
            info_text = (
                "<b style='color: #4da6ff; font-size: 14px;'>Change Delivery Directory</b><br>"
                "Selecting a new folder will initialize and scaffold project sequences and shots in the new location."
            )

        header_label = QLabel(info_text)
        header_label.setWordWrap(True)
        layout.addWidget(header_label)

        # Path input box
        group = QGroupBox("Target Delivery Location")
        group_layout = QHBoxLayout(group)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select external delivery directory...")
        if current_path:
            self.path_edit.setText(current_path)
        group_layout.addWidget(self.path_edit)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_folder)
        group_layout.addWidget(btn_browse)

        layout.addWidget(group)

        # Loader & Status Feedback
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #4da6ff; font-weight: bold; font-size: 11px;")
        self.status_lbl.setVisible(False)
        layout.addWidget(self.status_lbl)

        self.loader_bar = QProgressBar()
        self.loader_bar.setRange(0, 0)  # Animated indeterminate spinner
        self.loader_bar.setTextVisible(False)
        self.loader_bar.setFixedHeight(6)
        self.loader_bar.setVisible(False)
        layout.addWidget(self.loader_bar)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel" if not self.is_first_time else "Skip For Now")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("Confirm")
        self.btn_ok.setObjectName("primaryButton")
        self.btn_ok.clicked.connect(self.on_confirm)
        btn_layout.addWidget(self.btn_ok)

        layout.addLayout(btn_layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Client Delivery Root Directory", self.path_edit.text()
        )
        if folder:
            self.path_edit.setText(folder)

    def on_confirm(self):
        target = self.path_edit.text().strip()
        if not target:
            QMessageBox.warning(self, "Invalid Path", "Please specify a target delivery folder.")
            return

        target_path = Path(target)

        # Activate loader
        self.btn_ok.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.status_lbl.setText("⏳ Scaffolding delivery directory structure for all sequences & shots...")
        self.status_lbl.setVisible(True)
        self.loader_bar.setVisible(True)
        QApplication.processEvents()

        try:
            success, msg = DeliveryManager.setup_delivery_folder(target_path, self.sequences)
        finally:
            self.loader_bar.setVisible(False)
            self.status_lbl.setVisible(False)
            self.btn_ok.setEnabled(True)
            self.btn_cancel.setEnabled(True)

        if success:
            QMessageBox.information(self, "Delivery Scaffolded", msg)
            self.selected_path = str(target_path)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", msg)
