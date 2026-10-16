from __future__ import annotations

from rigflow.ui.qt import QtCore, QtGui, QtWidgets
from rigflow.ui import theme


class LinkOverlay(QtWidgets.QWidget):
    """Transparent, mouse-through layer connecting the selected hierarchy items."""

    def __init__(self, parent, source_tree, destination_tree):
        super().__init__(parent)
        self.source_tree = source_tree
        self.destination_tree = destination_tree
        self.match = None
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        parent.installEventFilter(self)
        source_tree.geometry_changed.connect(self.update)
        destination_tree.geometry_changed.connect(self.update)
        self.setGeometry(parent.rect())
        self.raise_()

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show, QtCore.QEvent.LayoutRequest):
            self.setGeometry(watched.rect())
            self.raise_()
            self.update()
        return False

    def set_match(self, match):
        self.match = match
        self.update()

    def paintEvent(self, event):
        if self.match is None:
            return
        start = self.source_tree.endpoint(self.match.source, self, True)
        end = self.destination_tree.endpoint(self.match.destination, self, False)
        if start is None or end is None:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        color = QtGui.QColor(theme.status_color(self.match.status))
        color.setAlpha(180)
        painter.setPen(QtGui.QPen(color, 2))
        path = QtGui.QPainterPath(QtCore.QPointF(start))
        distance = (end.x() - start.x()) * 0.3
        path.cubicTo(start.x() + distance, start.y(), end.x() - distance, end.y(), end.x(), end.y())
        painter.drawPath(path)
        painter.setBrush(color)
        painter.drawEllipse(start, 3, 3)
        painter.drawEllipse(end, 3, 3)
