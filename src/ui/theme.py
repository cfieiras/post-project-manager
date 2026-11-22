"""
Dark Theme Stylesheet and Palette for Post Project Manager.
Native Fusion dark palette combined with clean VFX styling to guarantee
crisp, high-contrast, fully functional arrows in QComboBox, QSpinBox, and QMenu.
"""

from pathlib import Path
from PySide6.QtGui import QColor, QIcon, QPalette, QPixmap
from PIL import Image, ImageDraw


def _ensure_icons_exist() -> dict[str, str]:
    """Generates crisp arrow PNG icons if missing and returns their resolved paths."""
    icons_dir = Path(__file__).resolve().parent / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    icons = {
        "down": icons_dir / "arrow_down_vfx.png",
        "down_hover": icons_dir / "arrow_down_hover.png",
        "up": icons_dir / "arrow_up_vfx.png",
        "up_hover": icons_dir / "arrow_up_hover.png",
        "right": icons_dir / "arrow_right_vfx.png",
        "right_hover": icons_dir / "arrow_right_hover.png",
    }

    def draw_arrow(path: Path, direction: str, color: tuple, size=(16, 16)):
        if path.exists():
            return
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        w, h = size
        cx, cy = w // 2, h // 2

        if direction == "down":
            points = [(cx - 4, cy - 2), (cx + 4, cy - 2), (cx, cy + 2)]
            draw.polygon(points, fill=color)
        elif direction == "up":
            points = [(cx - 4, cy + 2), (cx + 4, cy + 2), (cx, cy - 2)]
            draw.polygon(points, fill=color)
        elif direction == "right":
            points = [(cx - 2, cy - 4), (cx - 2, cy + 4), (cx + 2, cy)]
            draw.polygon(points, fill=color)

        img.save(path)

    draw_arrow(icons["down"], "down", (190, 190, 200, 255))
    draw_arrow(icons["down_hover"], "down", (77, 166, 255, 255))
    draw_arrow(icons["up"], "up", (190, 190, 200, 255))
    draw_arrow(icons["up_hover"], "up", (77, 166, 255, 255))
    draw_arrow(icons["right"], "right", (190, 190, 200, 255))
    draw_arrow(icons["right_hover"], "right", (255, 255, 255, 255))

    return {k: str(v.resolve()).replace("\\", "/") for k, v in icons.items()}


_ICONS = _ensure_icons_exist()


def get_app_icon() -> QIcon:
    """Returns the official QIcon for the application (supporting ICO and PNG)."""
    icons_dir = Path(__file__).resolve().parent / "icons"
    ico_path = icons_dir / "app_icon.ico"
    png_path = icons_dir / "app_icon.png"
    icon = QIcon()
    if ico_path.exists():
        icon.addFile(str(ico_path))
    if png_path.exists():
        icon.addFile(str(png_path))
    return icon


def get_app_icon_pixmap(size: int = 32) -> QPixmap:
    """Returns a high-quality QPixmap of the application icon scaled to size."""
    icon = get_app_icon()
    return icon.pixmap(size, size)


def get_dark_palette() -> QPalette:
    """Returns a high-contrast dark QPalette that powers native Fusion style widgets."""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#202022"))
    palette.setColor(QPalette.WindowText, QColor("#ffffff"))
    palette.setColor(QPalette.Base, QColor("#18181a"))
    palette.setColor(QPalette.AlternateBase, QColor("#222226"))
    palette.setColor(QPalette.ToolTipBase, QColor("#282830"))
    palette.setColor(QPalette.ToolTipText, QColor("#ffffff"))
    palette.setColor(QPalette.Text, QColor("#ffffff"))
    palette.setColor(QPalette.Button, QColor("#28282e"))
    palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.BrightText, QColor("#ff5252"))
    palette.setColor(QPalette.Link, QColor("#4da6ff"))
    palette.setColor(QPalette.Highlight, QColor("#0078d4"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return palette


DARK_STYLESHEET = f"""
QWidget {{
    background-color: #202022;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 12px;
}}

/* Group Boxes & Section Containers */
QGroupBox {{
    border: 1px solid #44444e;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: bold;
    color: #4da6ff;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    background-color: #202022;
}}

/* Buttons */
QPushButton {{
    background-color: #2d2d32;
    border: 1px solid #3d3d44;
    border-radius: 4px;
    padding: 6px 14px;
    color: #ffffff;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: #383840;
    border: 1px solid #4da6ff;
}}

QPushButton:pressed {{
    background-color: #1e1e24;
}}

QPushButton:disabled {{
    background-color: #242428;
    color: #666666;
    border-color: #2c2c30;
}}

/* Primary Accent Buttons */
QPushButton#primaryButton {{
    background-color: #0078d4;
    border: 1px solid #1084d8;
    color: #ffffff;
    font-weight: bold;
}}

QPushButton#primaryButton:hover {{
    background-color: #1084d8;
    border-color: #40a0ff;
}}

QPushButton#primaryButton:pressed {{
    background-color: #005a9e;
}}

/* Text Inputs */
QLineEdit, QTextEdit {{
    background-color: #18181a;
    border: 1px solid #38383e;
    border-radius: 4px;
    padding: 5px 8px;
    color: #ffffff;
    selection-background-color: #0078d4;
}}

QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid #4da6ff;
}}

/* Comboboxes - Crisp dedicated dropdown arrow */
QComboBox {{
    background-color: #18181a;
    border: 1px solid #38383e;
    border-radius: 4px;
    padding: 5px 26px 5px 8px;
    color: #ffffff;
    selection-background-color: #0078d4;
}}

QComboBox:hover, QComboBox:focus {{
    border: 1px solid #4da6ff;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid #2d2d34;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    background-color: #222226;
}}

QComboBox::drop-down:hover {{
    background-color: #2c2c34;
}}

QComboBox::down-arrow {{
    image: url({_ICONS['down']});
    width: 12px;
    height: 12px;
}}

QComboBox::down-arrow:hover {{
    image: url({_ICONS['down_hover']});
}}

QComboBox QAbstractItemView {{
    background-color: #1c1c1f;
    border: 1px solid #38383e;
    selection-background-color: #0078d4;
    color: #ffffff;
    padding: 4px;
}}

/* Spinboxes - High contrast up/down controls */
QSpinBox, QDoubleSpinBox {{
    background-color: #18181a;
    border: 1px solid #38383e;
    border-radius: 4px;
    padding: 5px 22px 5px 8px;
    color: #ffffff;
    selection-background-color: #0078d4;
}}

QSpinBox:hover, QDoubleSpinBox:hover,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid #4da6ff;
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #38383e;
    border-bottom: 1px solid #282830;
    border-top-right-radius: 4px;
    background-color: #242428;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background-color: #32323a;
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({_ICONS['up']});
    width: 10px;
    height: 10px;
}}

QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{
    image: url({_ICONS['up_hover']});
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #38383e;
    border-bottom-right-radius: 4px;
    background-color: #242428;
}}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: #32323a;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({_ICONS['down']});
    width: 10px;
    height: 10px;
}}

QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {{
    image: url({_ICONS['down_hover']});
}}

/* Checkboxes */
QCheckBox {{
    spacing: 8px;
    color: #dddddd;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #44444c;
    border-radius: 3px;
    background-color: #18181a;
}}

QCheckBox::indicator:hover {{
    border-color: #4da6ff;
}}

QCheckBox::indicator:checked {{
    background-color: #0078d4;
    border-color: #0078d4;
}}

/* Menus & Popups */
QMenu {{
    background-color: #1c1c20;
    border: 1px solid #383842;
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 26px 6px 14px;
    border-radius: 4px;
    color: #e0e0e0;
}}

QMenu::item:selected {{
    background-color: #0078d4;
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background-color: #33333c;
    margin: 4px 8px;
}}

QMenu::right-arrow {{
    image: url({_ICONS['right']});
    width: 10px;
    height: 10px;
    right: 8px;
}}

QMenu::right-arrow:selected {{
    image: url({_ICONS['right_hover']});
}}

/* Tree & Table Views */
QTreeWidget, QTableWidget {{
    background-color: #18181a;
    border: 1px solid #2e2e34;
    border-radius: 4px;
    alternate-background-color: #1f1f23;
    gridline-color: #2a2a30;
    color: #e2e2e2;
}}

QTreeWidget::item, QTableWidget::item {{
    padding: 4px 6px;
}}

QTreeWidget::item:hover, QTableWidget::item:hover {{
    background-color: #282830;
}}

QTreeWidget::item:selected, QTableWidget::item:selected {{
    background-color: #005a9e;
    color: #ffffff;
}}

QHeaderView::section {{
    background-color: #25252a;
    border: none;
    border-right: 1px solid #33333a;
    border-bottom: 1px solid #33333a;
    padding: 6px 10px;
    font-weight: bold;
    color: #b0b0b8;
}}

QHeaderView::down-arrow {{
    image: url({_ICONS['down']});
    width: 10px;
    height: 10px;
}}

QHeaderView::up-arrow {{
    image: url({_ICONS['up']});
    width: 10px;
    height: 10px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    border: none;
    background-color: #1c1c1f;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: #383840;
    border-radius: 5px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #4da6ff;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Status Bar */
QStatusBar {{
    background-color: #18181a;
    border-top: 1px solid #282830;
    color: #909090;
}}

/* Splitter Dividers */
QSplitter::handle {{
    background-color: #282830;
}}

QSplitter::handle:horizontal {{
    width: 6px;
    border-left: 1px solid #3d3d48;
    border-right: 1px solid #3d3d48;
}}

QSplitter::handle:vertical {{
    height: 6px;
    border-top: 1px solid #3d3d48;
    border-bottom: 1px solid #3d3d48;
}}

QSplitter::handle:hover {{
    background-color: #0078d4;
    border-color: #4da6ff;
}}

/* Section Divider Lines */
QFrame[frameShape="4"], QFrame[frameShape="5"],
QFrame[frameShape="HLine"], QFrame[frameShape="VLine"] {{
    background-color: #3d3d48;
    border: none;
    height: 1px;
}}
"""
