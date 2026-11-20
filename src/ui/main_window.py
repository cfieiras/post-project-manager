"""
Main Window for Post Project Manager.
Portable desktop application for creating, managing, and browsing VFX and Post projects.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QStatusBar
)

from ..core.pipeline import PipelineManager
from .create_dialog import ProjectDialog
from .template_dialog import TemplateDialog


def get_config_file() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config.json"
    return Path(__file__).resolve().parent.parent.parent / "config.json"


CONFIG_FILE = get_config_file()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Post Project Manager - v1.0.0")
        self.resize(1050, 650)
        self.setMinimumSize(850, 500)

        self.pm = PipelineManager()
        self.config = self.load_config()
        self.projects_cache: List[Dict[str, Any]] = []

        self.init_ui()

        # Load last path or default
        last_path = self.config.get("last_projects_root")
        if last_path and Path(last_path).exists():
            self.path_input.setText(last_path)
            self.refresh_projects()
        else:
            default_path = Path.home() / "Documents" / "Projects"
            default_path.mkdir(parents=True, exist_ok=True)
            self.path_input.setText(str(default_path))
            self.refresh_projects()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 1. Top Bar: Root directory selection
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Projects Root:"))

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select directory where projects are stored...")
        self.path_input.textChanged.connect(self.on_path_changed)
        top_bar.addWidget(self.path_input)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_root_dir)
        top_bar.addWidget(btn_browse)

        btn_open_root = QPushButton("Open Folder")
        btn_open_root.clicked.connect(self.open_root_in_explorer)
        top_bar.addWidget(btn_open_root)

        main_layout.addLayout(top_bar)

        # 2. Filter & Actions Toolbar
        actions_bar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter projects by name...")
        self.search_input.textChanged.connect(self.filter_projects)
        actions_bar.addWidget(self.search_input)

        actions_bar.addSpacing(15)

        btn_new = QPushButton("+ New Project")
        btn_new.setObjectName("primaryButton")
        btn_new.clicked.connect(self.open_create_dialog)
        actions_bar.addWidget(btn_new)

        self.btn_edit = QPushButton("✎ Modify Project")
        self.btn_edit.clicked.connect(self.open_edit_dialog)
        actions_bar.addWidget(self.btn_edit)

        self.btn_open_proj = QPushButton("📁 Open Explorer")
        self.btn_open_proj.clicked.connect(self.open_selected_in_explorer)
        actions_bar.addWidget(self.btn_open_proj)

        btn_template = QPushButton("⚙ Pipeline Manual")
        btn_template.clicked.connect(self.open_template_dialog)
        actions_bar.addWidget(btn_template)

        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.clicked.connect(self.refresh_projects)
        actions_bar.addWidget(btn_refresh)

        main_layout.addLayout(actions_bar)

        # 3. Project Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Project Code", "Pipeline Status", "Active Modules", "Sequences", "Shots", "Directory Path"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemDoubleClicked.connect(self.open_selected_in_explorer)
        main_layout.addWidget(self.table)

        # 4. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def load_config(self) -> Dict[str, Any]:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save config: {e}")

    def browse_root_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Projects Root Directory", self.path_input.text()
        )
        if dir_path:
            self.path_input.setText(dir_path)
            self.config["last_projects_root"] = dir_path
            self.save_config()
            self.refresh_projects()

    def on_path_changed(self, text: str):
        path = Path(text)
        if path.exists() and path.is_dir():
            self.config["last_projects_root"] = text
            self.save_config()
            self.refresh_projects()

    def refresh_projects(self):
        root = Path(self.path_input.text())
        if not root.exists() or not root.is_dir():
            self.table.setRowCount(0)
            self.status_bar.showMessage("Invalid root path.")
            return

        self.projects_cache = self.pm.scan_projects(root)
        self.filter_projects()

    def filter_projects(self):
        query = self.search_input.text().strip().lower()
        filtered = [
            p for p in self.projects_cache
            if not query or query in p["name"].lower()
        ]

        self.table.setRowCount(len(filtered))
        for row, p in enumerate(filtered):
            # 0. Name
            item_name = QTableWidgetItem(p["name"])
            item_name.setData(Qt.UserRole, p)
            item_name.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 0, item_name)

            # 1. Status
            status_text = "✔ Registered" if p["is_registered"] else "Unregistered"
            item_status = QTableWidgetItem(status_text)
            if p["is_registered"]:
                item_status.setForeground(Qt.green)
            else:
                item_status.setForeground(Qt.gray)
            item_status.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item_status)

            # 2. Modules Badges
            mods = p.get("active_modules", [])
            badge_str = " ".join([f"[{m.upper()}]" for m in mods]) if mods else "-"
            item_mods = QTableWidgetItem(badge_str)
            item_mods.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item_mods)

            # 3. Sequences
            item_seq = QTableWidgetItem(str(p.get("sequences_count", 0)))
            item_seq.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_seq)

            # 4. Shots
            item_shots = QTableWidgetItem(str(p.get("shots_count", 0)))
            item_shots.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, item_shots)

            # 5. Path
            item_path = QTableWidgetItem(p["path"])
            item_path.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 5, item_path)

        self.status_bar.showMessage(
            f"Showing {len(filtered)} of {len(self.projects_cache)} projects in {self.path_input.text()}"
        )

    def get_selected_project(self) -> Optional[Dict[str, Any]]:
        curr_row = self.table.currentRow()
        if curr_row < 0:
            return None
        item = self.table.item(curr_row, 0)
        return item.data(Qt.UserRole) if item else None

    def open_create_dialog(self):
        root = Path(self.path_input.text())
        if not root.exists():
            QMessageBox.warning(self, "Invalid Directory", "Please select a valid root directory first.")
            return

        dialog = ProjectDialog(
            pipeline_manager=self.pm,
            root_dir=root,
            edit_mode=False,
            parent=self
        )
        dialog.project_created.connect(lambda: self.refresh_projects())
        dialog.exec()

    def open_edit_dialog(self):
        proj = self.get_selected_project()
        if not proj:
            QMessageBox.information(self, "Selection", "Please select a project to modify.")
            return

        proj_path = Path(proj["path"])
        dialog = ProjectDialog(
            pipeline_manager=self.pm,
            root_dir=Path(self.path_input.text()),
            edit_mode=True,
            existing_meta=proj.get("meta"),
            project_path=proj_path,
            parent=self
        )
        dialog.project_created.connect(lambda: self.refresh_projects())
        dialog.exec()

    def open_template_dialog(self):
        dialog = TemplateDialog(pipeline_manager=self.pm, parent=self)
        dialog.exec()

    def open_selected_in_explorer(self):
        proj = self.get_selected_project()
        if not proj:
            return
        p_path = proj["path"]
        if sys.platform == "win32":
            os.startfile(p_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", p_path])
        else:
            subprocess.run(["xdg-open", p_path])

    def open_root_in_explorer(self):
        r_path = self.path_input.text()
        if Path(r_path).exists():
            if sys.platform == "win32":
                os.startfile(r_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", r_path])
            else:
                subprocess.run(["xdg-open", r_path])
