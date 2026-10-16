from __future__ import annotations

from rigflow.animation.clip import ClipStatus
from rigflow.ui.qt import QtCore, QtWidgets, Signal
from rigflow.ui.widgets.status_badge import StatusBadge
from rigflow.ui import theme


class ClipList(QtWidgets.QWidget):
    """Compact live clip list. Action signals always carry stable clip IDs."""
    map_requested = Signal(str)
    review_requested = Signal(str)
    transfer_requested = Signal(str)
    remove_requested = Signal(str)
    replace_requested = Signal(str)
    add_requested = Signal()
    clip_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Animation", "Convention / range / frames", "Status", "", "Actions"])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(142)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for col, width in ((1, 184), (2, 140), (3, 88), (4, 158)):
            self.table.setColumnWidth(col, width)
        layout.addWidget(self.table)
        self.table.itemSelectionChanged.connect(self._selected)
        self.set_clips([])

    def _selected(self):
        item = self.table.item(self.table.currentRow(), 0)
        if item:
            self.clip_selected.emit(item.data(QtCore.Qt.UserRole))

    def rowCount(self):
        return self.table.rowCount()

    def set_clips(self, clips, active_clip_id=None):
        blocker = QtCore.QSignalBlocker(self.table)
        for row in range(self.table.rowCount()):
            for col in (2, 3, 4):
                widget = self.table.cellWidget(row, col)
                if widget:
                    widget.hide()
        self.table.setRowCount(0)
        self.table.setVisible(bool(clips))
        self.table.setRowCount(len(clips))
        self.table.setMinimumHeight(min(4, max(1, len(clips))) * 56 + 40)
        colors = {ClipStatus.IMPORTED: theme.ACCENT, ClipStatus.MAPPED: theme.GREEN,
                  ClipStatus.NEEDS_REVIEW: theme.YELLOW, ClipStatus.PREVIEWING: theme.ACCENT,
                  ClipStatus.TRANSFERRED: theme.GREEN, ClipStatus.ERROR: theme.RED}
        for row, clip in enumerate(clips):
            self.table.setRowHeight(row, 56)
            item = QtWidgets.QTableWidgetItem(clip.name)
            item.setToolTip(clip.source_path or "Source from the current Maya scene")
            item.setData(QtCore.Qt.UserRole, clip.clip_id)
            self.table.setItem(row, 0, item)
            detail = QtWidgets.QTableWidgetItem("{}\n{} · {} frames".format(clip.convention, clip.range_label, clip.frame_count))
            detail.setToolTip("{} joints · {:g} fps".format(clip.joint_count, clip.fps))
            self.table.setItem(row, 1, detail)
            self.table.setCellWidget(row, 2, StatusBadge(clip.status.label, colors[clip.status]))
            edit = theme.button("Match", "Inspect and correct the source-to-destination mapping.")
            edit.clicked.connect(lambda checked=False, cid=clip.clip_id: self.map_requested.emit(cid))
            self.table.setCellWidget(row, 3, self._wrap(edit))
            actions = QtWidgets.QWidget()
            bar = QtWidgets.QHBoxLayout(actions)
            bar.setContentsMargins(4, 4, 4, 4)
            bar.setSpacing(4)
            review = theme.button("Transfer", "Preview and transfer this animation to the destination.")
            review.setEnabled(clip.mapping is not None)
            review.clicked.connect(lambda checked=False, cid=clip.clip_id: self.review_requested.emit(cid))
            bar.addWidget(review)
            more = theme.button("···", "Transfer, replace the source file, or remove this clip.")
            more.setFixedWidth(40)
            menu = QtWidgets.QMenu(more)
            for title, signal, tip in (
                ("Replace…", self.replace_requested, "Replace this clip with another file, keeping its list position."),
                ("Remove", self.remove_requested, "Remove this clip and its imported source nodes; scene sources are retained."),
            ):
                action = menu.addAction(title)
                action.setToolTip(tip)
                action.triggered.connect(lambda checked=False, cid=clip.clip_id, sig=signal: sig.emit(cid))
                if title.startswith("Transfer"):
                    action.setEnabled(clip.mapping is not None)
            more.setMenu(menu)
            bar.addWidget(more)
            self.table.setCellWidget(row, 4, actions)
            if clip.clip_id == active_clip_id:
                self.table.selectRow(row)
        del blocker

    @staticmethod
    def _wrap(widget):
        host = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(host)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(widget)
        return host
