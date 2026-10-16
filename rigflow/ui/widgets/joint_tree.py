from __future__ import annotations

from rigflow.ui.qt import QtCore, QtGui, QtWidgets, Signal
from rigflow.ui import theme


class JointTree(QtWidgets.QWidget):
    """Searchable hierarchy; joint identifiers are stored separately from labels."""
    joint_selected = Signal(str)
    joint_activated = Signal(str)
    geometry_changed = Signal()

    def __init__(self, title="Joints", parent=None):
        super().__init__(parent)
        self.items = {}
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(theme.label(title, heading=True))
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Filter joints…")
        self.search.setClearButtonEnabled(True)
        self.search.setToolTip("Search joint names; matching ancestors remain visible.")
        layout.addWidget(self.search)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(170)
        self.tree.setUniformRowHeights(True)
        self.tree.setIndentation(12)
        self.tree.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        layout.addWidget(self.tree, 1)
        self.search.textChanged.connect(self._filter)
        self.tree.currentItemChanged.connect(self._selected)
        self.tree.itemDoubleClicked.connect(lambda item, col: self.joint_activated.emit(item.data(0, QtCore.Qt.UserRole)))
        self.tree.verticalScrollBar().valueChanged.connect(self.geometry_changed)
        self.tree.horizontalScrollBar().valueChanged.connect(self.geometry_changed)
        self.tree.itemExpanded.connect(self.geometry_changed)
        self.tree.itemCollapsed.connect(self.geometry_changed)

    def set_skeleton(self, skeleton):
        self.tree.clear()
        self.items.clear()
        if skeleton is None:
            return
        for name in skeleton:
            joint = skeleton.get(name)
            item = QtWidgets.QTreeWidgetItem([joint.short_name])
            item.setData(0, QtCore.Qt.UserRole, joint.name)
            item.setToolTip(0, joint.name)
            self.items[joint.name] = item
        for name in skeleton:
            joint = skeleton.get(name)
            item = self.items[joint.name]
            if joint.parent in self.items:
                self.items[joint.parent].addChild(item)
            else:
                self.tree.addTopLevelItem(item)
        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)
        self._filter(self.search.text())

    def _filter(self, text):
        text = text.lower().strip()
        visible = set()
        for name, item in self.items.items():
            if text in name.lower():
                current = item
                while current is not None:
                    visible.add(current.data(0, QtCore.Qt.UserRole))
                    current = current.parent()
        for name, item in self.items.items():
            item.setHidden(name not in visible)
        self.geometry_changed.emit()

    def _selected(self, item, previous):
        if item is not None:
            self.joint_selected.emit(item.data(0, QtCore.Qt.UserRole))

    def selected_joint(self):
        item = self.tree.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item is not None else None

    def highlight(self, name, color=theme.ACCENT):
        old = self.tree.currentItem()
        if old is not None:
            old.setForeground(0, QtGui.QBrush())
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)
        item = self.items.get(name)
        if item is not None:
            if item.isHidden():
                self.search.clear()
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)
            item.setForeground(0, QtGui.QBrush(QtGui.QColor(color)))
        self.geometry_changed.emit()

    def endpoint(self, name, overlay, right=True):
        item = self.items.get(name)
        if item is None or item.isHidden():
            return None
        rect = self.tree.visualItemRect(item)
        if rect.isEmpty() or not self.tree.viewport().rect().intersects(rect):
            return None
        point = QtCore.QPoint(self.tree.viewport().width() - 5 if right else 5, rect.center().y())
        return overlay.mapFromGlobal(self.tree.viewport().mapToGlobal(point))
