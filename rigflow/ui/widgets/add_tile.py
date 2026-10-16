from rigflow.ui.qt import QtCore, QtGui, QtWidgets, Signal
from rigflow.ui import theme
from rigflow.ui.widgets.drop_area import DropArea


class AddTile(QtWidgets.QAbstractButton):
    def __init__(self, size=112, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("Add an animation from a file or a skeleton in the scene.")
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAttribute(QtCore.Qt.WA_Hover)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        active = self.underMouse() or self.hasFocus()
        color = theme.ACCENT if active else theme.BORDER_LIGHT
        painter.setPen(QtGui.QPen(QtGui.QColor(color), 1, QtCore.Qt.DashLine))
        painter.setBrush(QtGui.QColor("#263b40" if self.isDown() else "#30383a") if active else QtCore.Qt.NoBrush)
        painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1), 6, 6)
        painter.setPen(QtGui.QColor(theme.PRESSED if self.isDown() else theme.ACCENT if active else theme.MUTED))
        font = self.font()
        font.setPixelSize(44 if self.width() > 40 else 26)
        painter.setFont(font)
        painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "+")
        painter.end()


class AddAnimationArea(QtWidgets.QFrame):
    file_selected = Signal(str)
    add_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("sectionCard")
        self.setToolTip("Drop one .fbx, .ma or .mb animation anywhere in this area.")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addStretch()
        self.tile = AddTile()
        self.tile.clicked.connect(self.add_requested.emit)
        layout.addWidget(self.tile, 0, QtCore.Qt.AlignHCenter)
        title = theme.label("Add an animation", heading=True)
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        caption = theme.label("Drop an .fbx / .ma / .mb here, or pick an animated skeleton from the scene", muted=True)
        caption.setWordWrap(True)
        caption.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(caption)
        layout.addStretch()

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and DropArea.accepts(urls[0].toLocalFile()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and DropArea.accepts(urls[0].toLocalFile()):
            self.file_selected.emit(urls[0].toLocalFile())
            event.acceptProposedAction()
