"""Resolution independent RigFlow wordmark."""
from rigflow.ui.qt import QtCore, QtGui, QtWidgets
from rigflow.ui import brand, theme


class LogoWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 32)
        self.setToolTip("RigFlow · Animation Transfer for Maya")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        brand.paint_wordmark(painter, QtCore.QRectF(self.rect()), theme.TEXT)
        painter.end()
