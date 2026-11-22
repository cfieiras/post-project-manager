"""
Application Entry Point for Post Project Manager.
Can be executed directly via Python or compiled to a portable .exe with PyInstaller.
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.ui.theme import DARK_STYLESHEET, get_app_icon, get_dark_palette


def main():
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("vfx.post_project_manager.1.0")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(get_dark_palette())
    app.setStyleSheet(DARK_STYLESHEET)
    app.setWindowIcon(get_app_icon())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
