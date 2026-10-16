"""Step one: destination slots and a persistent animation library."""
from rigflow.skeleton.roles import REQUIRED_ROLES
from rigflow.ui.qt import QtCore, QtWidgets
from rigflow.ui import theme
from rigflow.ui.widgets.section_card import SectionCard
from rigflow.ui.widgets.status_badge import StatusBadge
from rigflow.ui.widgets.drop_area import DropArea
from rigflow.ui.widgets.clip_list import ClipList
from rigflow.ui.widgets.add_tile import AddTile, AddAnimationArea


class SetupView(QtWidgets.QWidget):
    def __init__(self, window):
        super().__init__()
        self.setObjectName("page")
        self.window = window
        self.session = window.session
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 16)
        layout.setSpacing(16)
        slots = QtWidgets.QHBoxLayout()
        slots.setSpacing(12)
        self.slot_cards = {}
        for name in ("Mesh", "Rig", "Anim"):
            card = SectionCard(name)
            card.setFixedHeight(164)
            card.setMinimumWidth(0)
            badge = StatusBadge("Not loaded", theme.GRAY)
            card.add_action(badge)
            detail = theme.label("No {} loaded".format(name.lower()), muted=True)
            detail.setWordWrap(True)
            detail.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            card.body.addWidget(detail, 1)
            card.badge, card.detail = badge, detail
            self.slot_cards[name] = card
            slots.addWidget(card, 1)
        self.model_section = self.slot_cards["Mesh"]
        self.rig_section = self.slot_cards["Rig"]
        self.animation_section = self.slot_cards["Anim"]
        for card, select, import_file in (
            (self.model_section, window.controller.set_model_from_selection, window.controller.import_model),
            (self.rig_section, window.controller.set_rig_from_selection, window.controller.import_rig),
        ):
            actions = QtWidgets.QHBoxLayout()
            actions.setSpacing(8)
            actions.addWidget(theme.button("Use selection", "Read this destination from the Maya selection.", select))
            drop = DropArea("Drop file")
            drop.layout().setContentsMargins(0, 0, 0, 0)
            drop.layout().itemAt(0).widget().hide()
            drop.hint.hide()
            drop.browse_button.setText("Browse…")
            drop.file_selected.connect(import_file)
            drop.rejected.connect(lambda text: self.session.status(text, "warning"))
            actions.addWidget(drop)
            card.body.addLayout(actions)
        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(theme.button("Add file…", "Import an animated skeleton from .fbx, .ma or .mb.", window.add_file))
        actions.addWidget(theme.button("From scene…", "Choose an animated skeleton already in Maya.", window.add_from_scene))
        self.animation_section.body.addLayout(actions)
        layout.addLayout(slots)
        self.main_area = QtWidgets.QStackedWidget()
        self.empty_area = AddAnimationArea()
        self.add_tile = self.empty_area.tile
        self.empty_area.add_requested.connect(window.show_add_menu)
        self.empty_area.file_selected.connect(window.add_path)
        self.populated_area = QtWidgets.QWidget()
        populated = QtWidgets.QVBoxLayout(self.populated_area)
        populated.setContentsMargins(0, 0, 0, 0)
        populated.setSpacing(12)
        self.clip_list = ClipList()
        self.clip_list.clip_selected.connect(self._activate)
        populated.addWidget(self.clip_list, 1)
        self.small_add_tile = AddTile(40)
        self.small_add_tile.clicked.connect(window.show_add_menu)
        populated.addWidget(self.small_add_tile, 0, QtCore.Qt.AlignHCenter)
        self.main_area.addWidget(self.empty_area)
        self.main_area.addWidget(self.populated_area)
        layout.addWidget(self.main_area, 1)
        layout.addWidget(theme.label("Geometry is optional. A destination rig is required.", muted=True))
        bottom = QtWidgets.QHBoxLayout()
        self.validation_label = theme.label("", muted=True)
        self.validation_label.setWordWrap(True)
        bottom.addWidget(self.validation_label, 1)
        self.validate_button = theme.button("Validate", "Check the active animation and destination, matching automatically if needed.", window.validate_active, True)
        bottom.addWidget(self.validate_button)
        self.next_button = theme.button("Next: Match ›", "Open the two-character matching workspace after validation.", self._next)
        self.next_button.setEnabled(False)
        bottom.addWidget(self.next_button)
        layout.addLayout(bottom)

    def _activate(self, clip_id):
        if self.session.active_clip_id != clip_id:
            self.session.set_active_clip(clip_id)

    def _next(self):
        if self.session.active_clip:
            self.window.open_match(self.session.active_clip_id)

    def refresh(self):
        model, rig, clip = self.session.model, self.session.rig, self.session.active_clip
        for card in self.slot_cards.values():
            card.badge.set_status("Not loaded", theme.GRAY)
        self.model_section.detail.setText("No geometry loaded\nOptional destination mesh")
        if model:
            self.model_section.detail.setText("{}\n{} meshes · {:,} vertices · {}".format(model.name, len(model.meshes), model.vertex_count, "Skinned" if model.skinned else "Unskinned"))
            self.model_section.badge.set_status("Loaded" if model.valid else "Needs attention", theme.GREEN if model.valid else theme.YELLOW)
        self.rig_section.detail.setText("No destination rig loaded\nSelect a skeleton root")
        if rig:
            count = len(set(REQUIRED_ROLES) & set(rig.labeling.roles() if rig.labeling else ()))
            self.rig_section.detail.setText("{} · {} joints\n{} · {}/{} required roles".format(rig.root, rig.joint_count, rig.convention, count, len(REQUIRED_ROLES)))
            ready = rig.valid and count == len(REQUIRED_ROLES)
            self.rig_section.badge.set_status("Loaded" if ready else "Needs attention", theme.GREEN if ready else theme.YELLOW)
            self.rig_section.detail.setToolTip("\n".join([rig.root] + rig.warnings))
        self.animation_section.detail.setText("No animation loaded\nAdd a file or use the scene")
        if clip:
            self.animation_section.detail.setText("{}\n{} · {} · {} frames".format(clip.name, clip.convention, clip.range_label, clip.frame_count))
            self.animation_section.badge.set_status("Needs attention" if clip.status.value in ("error", "needs_review") else "Loaded", theme.YELLOW if clip.status.value in ("error", "needs_review") else theme.GREEN)
        self.main_area.setCurrentWidget(self.populated_area if self.session.clips else self.empty_area)
        self.clip_list.set_clips(self.session.clips, self.session.active_clip_id)
        self.next_button.setEnabled(bool(clip and self.window._validated_clip == clip.clip_id and self.session.destination_ready))
