from rigflow.ui.qt import QtCore, QtGui, QtWidgets
from rigflow.ui import theme


class AddTile(QtWidgets.QAbstractButton):
    def __init__(self, size=112, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("Add a whole model from a file, Maya selection or the scene.")
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
