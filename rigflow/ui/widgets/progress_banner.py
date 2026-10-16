from __future__ import annotations

from rigflow.ui.qt import QtWidgets
from rigflow.ui import theme


class ProgressBanner(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        self.message = theme.label("Working…", muted=True)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.message)
        layout.addWidget(self.progress)
        self.hide()

    def start(self, message):
        self.message.setText(message)
        self.show()

    def finish(self):
        self.hide()
