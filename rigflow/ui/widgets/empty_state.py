from __future__ import annotations

from rigflow.ui.qt import QtCore, QtWidgets
from rigflow.ui import theme


class EmptyState(QtWidgets.QWidget):
    def __init__(self, hint, action=None, callback=None, glyph="◇", parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        icon = theme.label(glyph)
        icon.setStyleSheet("font-size: 25px; color: #7a7a7a;")
        layout.addWidget(icon)
        self.hint = theme.label(hint, muted=True)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint, 1)
        self.action = None
        if action:
            self.action = theme.button(action, hint, callback, primary=True)
            layout.addWidget(self.action)
