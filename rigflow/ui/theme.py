"""Maya-friendly palette and shared UI measurements."""
from __future__ import annotations

WINDOW = "#373737"
CARD = "#2f2f2f"
RAISED = "#3d3d3d"
BORDER = "#1f1f1f"
BORDER_LIGHT = "#4a4a4a"
TEXT = "#e6e6e6"
MUTED = "#a0a0a0"
ACCENT = "#5b9bd5"
HOVER = "#6fb0ea"
PRESSED = "#4a86bd"
GREEN = "#58b368"
YELLOW = "#e0b84c"
RED = "#d9534f"
GRAY = "#7a7a7a"
PURPLE = "#8e7cc3"
SPACING = (4, 8, 12, 16, 24)
RADIUS = 6
STATUS_COLORS = dict(green=GREEN, yellow=YELLOW, red=RED, unavailable=GRAY, excluded=PURPLE)


def status_color(status):
    """Accept a MatchStatus or its serialized value."""
    return STATUS_COLORS.get(getattr(status, "value", status), GRAY)


def stylesheet():
    return """
    QWidget { color: #e6e6e6; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
    QMainWindow, QWidget#page { background: #373737; }
    QFrame#sectionCard { background: #2f2f2f; border: 1px solid #1f1f1f; border-radius: 6px; }
    QLabel { background: transparent; border: none; }
    QLabel[muted="true"] { color: #a0a0a0; }
    QLabel[heading="true"] { font-size: 13px; font-weight: 600; }
    QLabel#brand { font-size: 24px; font-weight: 600; }
    QLabel#step { color: #5b9bd5; font-size: 11px; font-weight: 600; }
    QPushButton, QToolButton { background: #3d3d3d; border: 1px solid #4a4a4a;
        border-radius: 6px; padding: 7px 12px; min-height: 16px; }
    QPushButton:hover, QToolButton:hover { background: #484848; border-color: #6fb0ea; }
    QPushButton:pressed, QToolButton:pressed { background: #303030; border-color: #4a86bd; }
    QPushButton:focus, QToolButton:focus { border: 1px solid #5b9bd5; }
    QPushButton:disabled, QToolButton:disabled { color: #7a7a7a; background: #333333; border-color: #424242; }
    QPushButton[primary="true"] { background: #5b9bd5; color: #151e26; border-color: #5b9bd5; font-weight: 600; }
    QPushButton[primary="true"]:hover { background: #6fb0ea; }
    QPushButton[primary="true"]:pressed { background: #4a86bd; }
    QPushButton[primary="true"]:disabled { background: #3d4852; color: #89949d; border-color: #3d4852; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #282828; border: 1px solid #4a4a4a;
        border-radius: 6px; padding: 6px; selection-background-color: #4a86bd; }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #5b9bd5; }
    QTreeWidget, QTableWidget, QListWidget { background: #2f2f2f; alternate-background-color: #333333;
        border: 1px solid #4a4a4a; border-radius: 6px; outline: none; selection-background-color: #354b5d; }
    QTreeWidget::item, QListWidget::item { padding: 4px; }
    QTreeWidget::item:selected, QTableWidget::item:selected { background: #354b5d; }
    QHeaderView::section { background: #3d3d3d; color: #a0a0a0; border: none;
        border-bottom: 1px solid #4a4a4a; padding: 7px; font-size: 11px; }
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical { background: #2f2f2f; width: 10px; margin: 0; }
    QScrollBar::handle:vertical { background: #555555; border-radius: 4px; min-height: 24px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal { background: #2f2f2f; height: 10px; }
    QScrollBar::handle:horizontal { background: #555555; min-width: 24px; border-radius: 4px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    QMenuBar, QMenu, QStatusBar { background: #2f2f2f; }
    QMenuBar::item:selected, QMenu::item:selected { background: #354b5d; }
    QMenu::item { padding: 7px 24px; }
    QToolTip { background: #242424; color: #e6e6e6; border: 1px solid #5b9bd5; padding: 6px; }
    QProgressBar { background: #282828; border: none; border-radius: 3px; max-height: 5px; }
    QProgressBar::chunk { background: #5b9bd5; border-radius: 3px; }
    QSlider::groove:horizontal { height: 4px; background: #242424; border-radius: 2px; }
    QSlider::sub-page:horizontal { background: #5b9bd5; }
    QSlider::handle:horizontal { background: #5b9bd5; width: 12px; margin: -4px 0; border-radius: 6px; }
    QCheckBox { spacing: 6px; }
    """


def button(text, tooltip, callback=None, primary=False, parent=None):
    """Build a consistently styled action with an explicit explanation."""
    from rigflow.ui.qt import QtWidgets
    widget = QtWidgets.QPushButton(text, parent)
    widget.setToolTip(tooltip)
    widget.setProperty("primary", primary)
    if callback is not None:
        widget.clicked.connect(lambda checked=False: callback())
    return widget


def label(text, heading=False, muted=False):
    from rigflow.ui.qt import QtWidgets
    widget = QtWidgets.QLabel(text)
    widget.setProperty("heading", heading)
    widget.setProperty("muted", muted)
    return widget
