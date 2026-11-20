"""
Dark Theme Stylesheet for Post Project Manager.
Inspired by modern VFX and Post-Production software (Nuke, Unreal, DaVinci Resolve).
"""

DARK_STYLESHEET = """
QWidget {
    background-color: #202022;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 12px;
}

/* Group Boxes */
QGroupBox {
    border: 1px solid #333338;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: bold;
    color: #4da6ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #202022;
}

/* Buttons */
QPushButton {
    background-color: #2d2d32;
    border: 1px solid #3d3d44;
    border-radius: 4px;
    padding: 6px 14px;
    color: #ffffff;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #383840;
    border: 1px solid #4da6ff;
}

QPushButton:pressed {
    background-color: #1e1e24;
}

QPushButton:disabled {
    background-color: #242428;
    color: #666666;
    border-color: #2c2c30;
}

/* Primary Accent Buttons */
QPushButton#primaryButton {
    background-color: #0078d4;
    border: 1px solid #1084d8;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#primaryButton:hover {
    background-color: #1084d8;
    border-color: #40a0ff;
}

QPushButton#primaryButton:pressed {
    background-color: #005a9e;
}

/* Text Inputs and Combos */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
    background-color: #18181a;
    border: 1px solid #38383e;
    border-radius: 4px;
    padding: 5px 8px;
    color: #ffffff;
    selection-background-color: #0078d4;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #4da6ff;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #a0a0a0;
    margin-right: 6px;
}

QComboBox QAbstractItemView {
    background-color: #18181a;
    border: 1px solid #38383e;
    selection-background-color: #0078d4;
    color: #ffffff;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #dddddd;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #44444c;
    border-radius: 3px;
    background-color: #18181a;
}

QCheckBox::indicator:hover {
    border-color: #4da6ff;
}

QCheckBox::indicator:checked {
    background-color: #0078d4;
    border-color: #0078d4;
}

/* Tree & Table Views */
QTreeWidget, QTableWidget {
    background-color: #18181a;
    border: 1px solid #2e2e34;
    border-radius: 4px;
    alternate-background-color: #1f1f23;
    gridline-color: #2a2a30;
    color: #e2e2e2;
}

QTreeWidget::item, QTableWidget::item {
    padding: 4px 6px;
}

QTreeWidget::item:hover, QTableWidget::item:hover {
    background-color: #282830;
}

QTreeWidget::item:selected, QTableWidget::item:selected {
    background-color: #005a9e;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #25252a;
    border: none;
    border-right: 1px solid #33333a;
    border-bottom: 1px solid #33333a;
    padding: 6px 10px;
    font-weight: bold;
    color: #b0b0b8;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background-color: #1c1c1f;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #383840;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4da6ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Status Bar */
QStatusBar {
    background-color: #18181a;
    border-top: 1px solid #282830;
    color: #909090;
}
"""
