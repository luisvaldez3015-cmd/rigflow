"""One complete model, with read-only detection slots."""
from rigflow.ui.qt import QtCore, QtWidgets, Signal
from rigflow.ui import theme
from rigflow.ui.widgets.section_card import SectionCard
from rigflow.ui.widgets.status_badge import StatusBadge
from rigflow.ui.widgets.drop_area import DropArea


class ModelCard(SectionCard):
    replace_requested = Signal(str)
    remove_requested = Signal(str)
    file_dropped = Signal(str, str)

    def __init__(self, character, label, parent=None):
        super().__init__(label, parent=parent)
        self.character_id = character.character_id
        self.setAcceptDrops(True)
        self.setMinimumWidth(0)
        self.name_label = theme.label("")
        self.name_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.body.addWidget(self.name_label)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.slots = {}
        for name in ("Mesh", "Rig", "Anim"):
            tile = QtWidgets.QFrame()
            tile.setStyleSheet("QFrame { background: #353535; border-radius: 5px; }")
            column = QtWidgets.QVBoxLayout(tile)
            column.setContentsMargins(10, 10, 10, 10)
            column.setSpacing(8)
            column.addWidget(theme.label(name, heading=True))
            tile.badge = StatusBadge("None", theme.GRAY)
            column.addWidget(tile.badge, 0, QtCore.Qt.AlignLeft)
            tile.detail = theme.label("", muted=True)
            tile.detail.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            column.addWidget(tile.detail)
            row.addWidget(tile, 1)
            self.slots[name] = tile
        self.body.addLayout(row)
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        self.replace_button = theme.button("Replace…", "Replace this whole model from a file.",
            lambda: self.replace_requested.emit(self.character_id))
        self.remove_button = theme.button("Remove", "Remove this model and its owned import and source clip.",
            lambda: self.remove_requested.emit(self.character_id))
        actions.addWidget(self.replace_button)
        actions.addWidget(self.remove_button)
        self.body.addLayout(actions)
        self.set_character(character, label)

    def set_character(self, character, label):
        self.character_id = character.character_id
        self.title_label.setText(label)
        self.name_label.setText(character.name)
        self.name_label.setToolTip(character.source_path or character.name)
        values = {
            "Mesh": (character.has_mesh, "{:,} vertices".format(character.mesh.vertex_count) if character.has_mesh else "No geometry", character.mesh),
            "Rig": (character.has_rig, "{} joints".format(character.rig.joint_count) if character.has_rig else "No skeleton", character.rig),
            "Anim": (character.has_anim, "{} frames".format(character.anim.frame_count) if character.has_anim else "No keys", character.anim),
        }
        for name, (present, detail, slot) in values.items():
            tile = self.slots[name]
            tile.badge.set_status("Detected" if present else "None", theme.GREEN if present else theme.GRAY)
            tile.detail.setText(detail)
            tile.setToolTip(slot.describe() if slot else detail)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and DropArea.accepts(urls[0].toLocalFile()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and DropArea.accepts(urls[0].toLocalFile()):
            self.file_dropped.emit(self.character_id, urls[0].toLocalFile())
            event.acceptProposedAction()
