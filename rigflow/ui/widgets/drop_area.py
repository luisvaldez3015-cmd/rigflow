from __future__ import annotations

import os
from rigflow.ui.qt import QtCore, QtWidgets, Signal
from rigflow.ui import theme

FILE_FILTER = "Models (*.fbx *.ma *.mb *.obj)"


class DropArea(QtWidgets.QFrame):
    """File drop target and file chooser accepting Maya, FBX and OBJ models."""
    file_selected = Signal(str)
    rejected = Signal(str)

    def __init__(self, hint="Drop an FBX, Maya or OBJ file here", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setToolTip("Drop a local .fbx, .ma, .mb or .obj file, or browse to import it.")
        self._style(False)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        icon = theme.label("↥")
        icon.setStyleSheet("font-size: 23px; color: #a0a0a0;")
        layout.addWidget(icon)
        self.hint = theme.label(hint, muted=True)
        layout.addWidget(self.hint, 1)
        self.browse_button = theme.button("Browse / Import", "Choose an FBX, Maya or OBJ model to import.", self.browse)
        layout.addWidget(self.browse_button)

    def _style(self, active):
        self.setStyleSheet("DropArea { border: 1px dashed %s; border-radius: 6px; background: #303030; }" %
                           (theme.ACCENT if active else theme.BORDER_LIGHT))

    @staticmethod
    def accepts(path):
        return os.path.splitext(path)[1].lower() in (".fbx", ".ma", ".mb", ".obj")

    def browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import file", "", FILE_FILTER)
        if path:
            self.file_selected.emit(path)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and self.accepts(urls[0].toLocalFile()):
            self._style(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._style(False)
        event.accept()

    def dropEvent(self, event):
        self._style(False)
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and self.accepts(urls[0].toLocalFile()):
            self.file_selected.emit(urls[0].toLocalFile())
            event.acceptProposedAction()
        else:
            self.rejected.emit("Choose one local .fbx, .ma, .mb or .obj file.")
            event.ignore()
