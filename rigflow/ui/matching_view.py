from rigflow.core.session import SessionEvent
from rigflow.mapping.model import MatchStatus
from rigflow.ui.qt import QtCore, QtWidgets, Signal
from rigflow.ui import theme
from rigflow.ui.widgets.viewport_panel import ViewportPanel
from rigflow.ui.widgets.joint_tree import JointTree
from rigflow.ui.widgets.mapping_table import MappingTable
from rigflow.ui.widgets.link_overlay import LinkOverlay
from rigflow.ui.widgets.status_badge import StatusBadge


class MatchingView(QtWidgets.QWidget):
    back_requested = Signal()
    review_requested = Signal(str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.controller, self.clip_id = controller, None
        self._source = self._destination = None
        self._pair = (None, None)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 16)
        layout.setSpacing(12)
        self.title = theme.label("New animation", heading=True)
        layout.addWidget(self.title)
        panels = QtWidgets.QHBoxLayout()
        panels.setSpacing(12)
        self.source_viewport = ViewportPanel("Model A · source", controller, "source")
        self.destination_viewport = ViewportPanel("Model B · destination", controller, "destination")
        panels.addWidget(self.source_viewport, 1)
        controls = QtWidgets.QWidget()
        controls.setObjectName("page")
        tools = QtWidgets.QVBoxLayout(controls)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(8)
        tools.addStretch()
        self.match_button = theme.button("Match", "Match the remembered A and B joints. A's role takes precedence.", self.link_selected, True)
        self.link_button = self.match_button
        self.unmatch_button = theme.button("Unmatch", "Drop the selected role's destination. Reset to automatic restores it.", self.unmatch)
        tools.addWidget(self.match_button)
        tools.addWidget(self.unmatch_button)
        tools.addWidget(theme.button("Auto-match", "Recompute automatic matches while preserving manual overrides.", self.auto_match))
        tools.addSpacing(8)
        tools.addWidget(theme.label("Selection", heading=True))
        self.source_selection = theme.label("A: —", muted=True)
        self.destination_selection = theme.label("B: —", muted=True)
        for readout in (self.source_selection, self.destination_selection):
            readout.setWordWrap(True)
            readout.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
            readout.setToolTip("Pick a joint in Maya or double-click it in Details. Each side is remembered independently.")
            tools.addWidget(readout)
        tools.addSpacing(8)
        self.badges = {}
        for status in MatchStatus:
            badge = StatusBadge("0 " + status.value, theme.status_color(status))
            self.badges[status] = badge
            tools.addWidget(badge)
        tools.addStretch()
        controls_scroll = QtWidgets.QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        controls_scroll.setFixedWidth(140)
        controls_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        controls_scroll.setWidget(controls)
        panels.addWidget(controls_scroll)
        panels.addWidget(self.destination_viewport, 1)
        layout.addLayout(panels, 1)
        self.details_toggle = QtWidgets.QToolButton()
        self.details_toggle.setText("Details")
        self.details_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.details_toggle.setArrowType(QtCore.Qt.RightArrow)
        self.details_toggle.setCheckable(True)
        self.details_toggle.setToolTip("Show joint hierarchies, mapping rows, exclusions and presets.")
        self.details_toggle.toggled.connect(self.set_details_expanded)
        layout.addWidget(self.details_toggle, 0, QtCore.Qt.AlignLeft)
        self.details = QtWidgets.QWidget()
        detail_layout = QtWidgets.QVBoxLayout(self.details)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)
        self.workspace = QtWidgets.QWidget()
        workspace_layout = QtWidgets.QHBoxLayout(self.workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.source_tree = JointTree("A · source joints")
        self.destination_tree = JointTree("B · destination joints")
        self.mapping_table = MappingTable()
        self.mapping_table.setHorizontalHeaderLabels(["Status", "Role", "A joint", "B joint", "Conf.", "Manual", "Exclude"])
        self.splitter.addWidget(self.source_tree)
        self.splitter.addWidget(self.mapping_table)
        self.splitter.addWidget(self.destination_tree)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([180, 720, 180])
        workspace_layout.addWidget(self.splitter)
        self.overlay = LinkOverlay(self.workspace, self.source_tree, self.destination_tree)
        detail_layout.addWidget(self.workspace, 1)
        presets = QtWidgets.QHBoxLayout()
        presets.addWidget(theme.button("Load preset…", "Load a mapping preset and validate joint names.", self.load_preset))
        presets.addWidget(theme.button("Save preset…", "Save mapping, manual corrections and exclusions.", self.save_preset))
        presets.addStretch()
        presets.addWidget(theme.button("Reset to automatic", "Remove manual overrides and restore automatic matches.", self.reset_manual))
        detail_layout.addLayout(presets)
        self.details.setFixedHeight(260)
        self.details.hide()
        layout.addWidget(self.details)
        self.validation_label = theme.label("Choose a source and destination skeleton.", muted=True)
        self.validation_label.setWordWrap(True)
        self.validation_label.setMaximumHeight(44)
        layout.addWidget(self.validation_label)
        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(theme.button("‹ Back", "Return to Setup.", self.back_requested.emit))
        bottom.addStretch()
        self.review_button = theme.button("Next: Transfer ›", "Preview the animation when validation has no errors.", self.review, True)
        bottom.addWidget(self.review_button)
        layout.addLayout(bottom)
        self.mapping_table.role_selected.connect(self._highlight)
        self.mapping_table.exclusion_changed.connect(self._exclude)
        self.source_tree.joint_activated.connect(lambda joint: self._tree_selection(joint, False))
        self.destination_tree.joint_activated.connect(lambda joint: self._tree_selection(joint, True))
        self.splitter.splitterMoved.connect(lambda *_: self.overlay.update())
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.poll_selection)
        self._unsubscribe = controller.session.subscribe(self._event)
        self._show_pair()

    def set_details_expanded(self, expanded):
        self.details_toggle.setChecked(expanded)
        self.details_toggle.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)
        self.details.setVisible(expanded)
        self.overlay.update()

    def set_clip(self, clip_id):
        self.clip_id = clip_id
        self.controller.session.set_active_clip(clip_id)
        clip = self.controller.session.get_clip(clip_id)
        self.set_details_expanded(False)
        if clip and clip.mapping is None and self.controller.session.destination_ready:
            self.controller.auto_map(clip_id)
        self.refresh()

    def activate(self):
        self.controller.begin_selection(self.clip_id)
        self.poll_selection()
        self.timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        if self.clip_id:
            self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        self.release_viewports()
        super().hideEvent(event)

    def poll_selection(self):
        if self.clip_id and self.isVisible():
            self._pair = self.controller.selected_pair(self.clip_id)
            self._show_pair()

    def _tree_selection(self, joint, destination):
        self.controller.remember_selected(self.clip_id, joint, destination)
        self._pair = self.controller.selected_pair(self.clip_id)
        self._show_pair()

    def _role(self):
        if not self.controller.session.get_clip(self.clip_id):
            return None
        return self.controller.selection_role(self.clip_id, *self._pair) or self.mapping_table.selected_role()

    def _show_pair(self):
        for label, prefix, joint in zip((self.source_selection, self.destination_selection), ("A", "B"), self._pair):
            label.setText("{}: {}".format(prefix, joint.rsplit("|", 1)[-1] if joint else "—"))
            label.setToolTip(joint or "Select a joint in Maya, or double-click a joint in Details.")
        self.match_button.setEnabled(bool(all(self._pair) and self._role()))
        self.unmatch_button.setEnabled(bool(self._role()))

    def _event(self, event, payload):
        if event in (SessionEvent.CLIPS_CHANGED, SessionEvent.RIG_CHANGED) and self.clip_id:
            self.refresh()

    def refresh(self):
        clip = self.controller.session.get_clip(self.clip_id)
        rig = self.controller.session.rig
        if clip is None:
            self.mapping_table.set_mapping(None)
            self.review_button.setEnabled(False)
            return
        self.title.setText("New animation · " + clip.name)
        destination = rig.skeleton if rig else None
        if clip.source_skeleton is not self._source:
            self._source = clip.source_skeleton
            self.source_tree.set_skeleton(self._source)
        if destination is not self._destination:
            self._destination = destination
            self.destination_tree.set_skeleton(destination)
        session = self.controller.session
        source, target = session.source, session.destination
        self.source_viewport.configure(self.controller.viewport_nodes(self.clip_id),
            session.label_for(source.character_id) + " · " + source.name if source else "Source · " + clip.name)
        self.destination_viewport.configure(self.controller.viewport_nodes(self.clip_id, destination=True),
            session.label_for(target.character_id) + " · " + target.name if target else "Destination · " + (rig.name if rig else "Choose a rig"))
        self.mapping_table.set_mapping(clip.mapping)
        counts = clip.mapping.summary() if clip.mapping else {}
        for status, badge in self.badges.items():
            badge.set_status("{} {}".format(counts.get(status.value, 0), status.value.title()), theme.status_color(status))
        report = self.controller.validate(self.clip_id)
        self.review_button.setEnabled(report.ok)
        detail = str((report.errors or report.warnings)[0]) if report.issues else "Mapping validated. Ready to transfer."
        self.validation_label.setText("{} errors · {} warnings  —  {}".format(len(report.errors), len(report.warnings), detail))
        self.validation_label.setToolTip("\n".join(str(issue) for issue in report.issues) or detail)
        self._highlight(self.mapping_table.selected_role())

    def _highlight(self, role):
        clip = self.controller.session.get_clip(self.clip_id)
        match = clip.mapping.matches.get(role) if clip and clip.mapping else None
        self.overlay.set_match(match)
        self.source_tree.highlight(match.source if match else None, theme.status_color(match.status) if match else theme.ACCENT)
        self.destination_tree.highlight(match.destination if match else None, theme.status_color(match.status) if match else theme.ACCENT)
        self._show_pair()

    def _exclude(self, role, excluded):
        if self.clip_id:
            QtCore.QTimer.singleShot(0, lambda cid=self.clip_id, r=role, ex=excluded: self.controller.set_excluded(cid, r, ex))

    def _clear_pair(self):
        self.controller.clear_selected_pair(self.clip_id)
        self._pair = (None, None)
        self._show_pair()

    def link_selected(self):
        role = self._role()
        source, destination = self._pair
        if role and source and destination:
            if self.controller.set_manual_match(self.clip_id, role, source, destination):
                self._clear_pair()
        else:
            self.controller.session.status("Select an A joint and a B joint in Maya or Details.", "warning")

    def unmatch(self):
        role = self._role()
        clip = self.controller.session.get_clip(self.clip_id)
        match = clip.mapping.matches.get(role) if clip and clip.mapping else None
        source = self._pair[0] or (match.source if match else None)
        if role and self.controller.set_manual_match(self.clip_id, role, source, None):
            self._clear_pair()
            self.controller.session.status("{} unmatched. Select a new pair and Match, or use Reset to automatic to restore it. Auto-match preserves manual overrides.".format(role), "warning")

    def auto_match(self):
        if self.clip_id:
            self.controller.auto_map(self.clip_id)

    def reset_manual(self):
        if self.clip_id and QtWidgets.QMessageBox.question(self, "Reset manual mapping?", "Remove all manual corrections? Exclusions are kept.", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
            self.controller.clear_manual(self.clip_id)

    def review(self):
        if self.clip_id and self.controller.validate(self.clip_id).ok:
            self.review_requested.emit(self.clip_id)

    def save_preset(self):
        if self.clip_id:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save mapping", "mapping.rigflow.json", "RigFlow mapping (*.json)")
            if path:
                self.controller.save_preset(self.clip_id, path)

    def load_preset(self):
        if self.clip_id:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load mapping", "", "RigFlow mapping (*.json)")
            if path:
                self.controller.load_preset(self.clip_id, path)

    def release_viewports(self):
        self.source_viewport.release()
        self.destination_viewport.release()

    def resizeEvent(self, event):
        self.details.setFixedHeight(max(180, min(260, self.height() - 330)))
        super().resizeEvent(event)

    def deactivate(self):
        self.timer.stop()
        if self.clip_id:
            self.controller.clear_selected_pair(self.clip_id)
        self._pair = (None, None)
        self.release_viewports()

    def dispose(self):
        self.deactivate()
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def closeEvent(self, event):
        self.dispose()
        super().closeEvent(event)
