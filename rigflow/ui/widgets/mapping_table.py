from __future__ import annotations

from rigflow.skeleton.roles import display_name
from rigflow.ui.qt import QtCore, QtGui, QtWidgets, Signal
from rigflow.ui.widgets.status_badge import StatusBadge
from rigflow.ui import theme


class MappingTable(QtWidgets.QTableWidget):
    """One row per sorted JointMatch with semantic status and editable exclusions."""
    role_selected = Signal(str)
    exclusion_changed = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(0, 7, parent)
        self.matches = []
        self.setHorizontalHeaderLabels(["Status", "Role", "Source joint", "Destination joint", "Conf.", "Manual", "Exclude"])
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(32)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.horizontalHeader().setMinimumSectionSize(42)
        for col, width in enumerate((106, 110, 140, 140, 50, 56, 56)):
            self.setColumnWidth(col, width)
        self.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.itemSelectionChanged.connect(self._selected)
        self.itemChanged.connect(self._changed)
        self.setToolTip("Select a role to highlight both joints. Choose joints in the trees to correct it.")

    def set_mapping(self, mapping):
        role = self.selected_role()
        blocker = QtCore.QSignalBlocker(self)
        for row in range(self.rowCount()):
            badge = self.cellWidget(row, 0)
            if badge:
                badge.hide()
        self.setRowCount(0)
        self.matches = mapping.sorted_matches() if mapping else []
        self.setRowCount(len(self.matches))
        for row, match in enumerate(self.matches):
            values = ["", display_name(match.role), match.source or "—",
                      match.destination or "—", "{:.0%}".format(match.confidence), "Yes" if match.manual else "—", ""]
            notes = "\n".join(match.notes) or "No additional match notes."
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setData(QtCore.Qt.UserRole, match.role)
                item.setToolTip((value + "\n" + notes).strip())
                if col >= 4:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                if col == 6:
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(QtCore.Qt.Checked if match.excluded else QtCore.Qt.Unchecked)
                    item.setToolTip("Exclude this role from transfer. Required roles cannot be excluded.")
                self.setItem(row, col, item)
            badge = StatusBadge(match.status.value.title(), theme.status_color(match.status))
            badge.setToolTip(notes)
            self.setCellWidget(row, 0, badge)
        del blocker
        if self.matches:
            rows = [i for i, match in enumerate(self.matches) if match.role == role]
            self.selectRow(rows[0] if rows else 0)

    def selected_role(self):
        row = self.currentRow()
        return self.matches[row].role if 0 <= row < len(self.matches) else None

    def _selected(self):
        role = self.selected_role()
        if role:
            self.role_selected.emit(role)

    def _changed(self, item):
        if item.column() == 6:
            self.exclusion_changed.emit(item.data(QtCore.Qt.UserRole), item.checkState() == QtCore.Qt.Checked)
