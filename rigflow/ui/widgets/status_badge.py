from __future__ import annotations

from rigflow.ui.qt import QtWidgets, QtGui
from rigflow.ui import theme


class StatusBadge(QtWidgets.QWidget):
    """A semantic color dot plus text; status is never encoded by color alone."""

    def __init__(self, text="Unavailable", color=theme.GRAY, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)
        self.dot = QtWidgets.QLabel()
        self.dot.setFixedSize(7, 7)
        self.label = QtWidgets.QLabel()
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        layout.addStretch()
        self.set_status(text, color)

    def set_status(self, text, color):
        self.color = QtGui.QColor(color)
        self.label.setText(text)
        self.dot.setStyleSheet("background: {}; border-radius: 3px;".format(color))
        self.setToolTip(text)
