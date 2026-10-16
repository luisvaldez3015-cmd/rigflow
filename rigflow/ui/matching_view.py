from __future__ import annotations

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
        self.controller = controller
        self.clip_id = None
        self._source = None
        self._destination = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(theme.button("‹ Back", "Return to your model, rig and animations.", self.back_requested.emit))
        self.title = theme.label("Match skeletons", heading=True)
        header.addWidget(self.title)
        header.addStretch()
        for title, callback, tip in (
            ("Load preset…", self.load_preset, "Load a saved mapping and validate its joint names."),
            ("Save preset…", self.save_preset, "Save this mapping, manual overrides and exclusions as JSON."),
        ):
            header.addWidget(theme.button(title, tip, callback))
        layout.addLayout(header)
        self.vertical_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        previews = QtWidgets.QWidget()
        panels = QtWidgets.QHBoxLayout(previews)
        panels.setContentsMargins(0, 0, 0, 0)
        panels.setSpacing(12)
        self.source_viewport = ViewportPanel("Source", controller, "source")
        self.destination_viewport = ViewportPanel("Destination", controller, "destination")
        panels.addWidget(self.source_viewport)
        panels.addWidget(self.destination_viewport)
        self.vertical_splitter.addWidget(previews)
        self.workspace = QtWidgets.QWidget()
        work_layout = QtWidgets.QVBoxLayout(self.workspace)
        work_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.source_tree = JointTree("Source hierarchy")
        self.destination_tree = JointTree("Destination hierarchy")
        table_host = QtWidgets.QWidget()
        center = QtWidgets.QVBoxLayout(table_host)
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(8)
        center.addWidget(theme.label("Joint mapping", heading=True))
        center.addWidget(theme.label("Select a role, choose two joints, then link them.", muted=True))
        self.mapping_table = MappingTable()
        center.addWidget(self.mapping_table, 1)
        self.splitter.addWidget(self.source_tree)
        self.splitter.addWidget(table_host)
        self.splitter.addWidget(self.destination_tree)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([190, 650, 190])
        work_layout.addWidget(self.splitter)
        self.overlay = LinkOverlay(self.workspace, self.source_tree, self.destination_tree)
        self.vertical_splitter.addWidget(self.workspace)
        self.vertical_splitter.setStretchFactor(1, 1)
        self.vertical_splitter.setSizes([180, 340])
        layout.addWidget(self.vertical_splitter, 1)
        tools = QtWidgets.QHBoxLayout()
        self.link_button = theme.button("Link selected", "Assign the selected joints to the selected role as a manual match.", self.link_selected)
        tools.addWidget(self.link_button)
        tools.addWidget(theme.button("Auto-match", "Recompute matches; keep your manual corrections and exclusions.", self.auto_match))
        tools.addWidget(theme.button("Reset to automatic", "Confirm removal of all manual overrides, then recompute.", self.reset_manual))
        tools.addStretch()
        self.review_button = theme.button("Review Animation ›", "Preview the mapped animation. Resolve validation errors first.", self.review, True)
        tools.addWidget(self.review_button)
        layout.addLayout(tools)
        self.summary_layout = QtWidgets.QHBoxLayout()
        self.badges = {}
        for status in MatchStatus:
            badge = StatusBadge("0 " + status.value, theme.status_color(status))
            self.badges[status] = badge
            self.summary_layout.addWidget(badge)
        self.summary_layout.addStretch()
        layout.addLayout(self.summary_layout)
        self.validation_label = theme.label("Choose a source and destination skeleton.", muted=True)
        self.validation_label.setWordWrap(True)
        self.validation_label.setMaximumHeight(46)
        layout.addWidget(self.validation_label)
        self.mapping_table.role_selected.connect(self._highlight)
        self.mapping_table.exclusion_changed.connect(self._exclude)
        self.source_tree.joint_activated.connect(lambda _: self.link_selected())
        self.destination_tree.joint_activated.connect(lambda _: self.link_selected())
        self.source_tree.joint_selected.connect(lambda _: self._update_link())
        self.destination_tree.joint_selected.connect(lambda _: self._update_link())
        self.splitter.splitterMoved.connect(lambda *_: self.overlay.update())
        self._unsubscribe = controller.session.subscribe(self._event)
        self._update_link()

    def set_clip(self, clip_id):
        self.clip_id = clip_id
        self.controller.session.set_active_clip(clip_id)
        clip = self.controller.session.get_clip(clip_id)
        if clip and clip.mapping is None and self.controller.session.destination_ready:
            self.controller.auto_map(clip_id)
        self.refresh()

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
        self.title.setText("Match skeletons · " + clip.name)
        destination = rig.skeleton if rig else None
        if clip.source_skeleton is not self._source:
            self._source = clip.source_skeleton
            self.source_tree.set_skeleton(self._source)
        if destination is not self._destination:
            self._destination = destination
            self.destination_tree.set_skeleton(destination)
        self.source_viewport.configure(self.controller.viewport_nodes(self.clip_id), "Source · {} · {}".format(clip.name, clip.convention))
        nodes = self.controller.viewport_nodes(self.clip_id, destination=True)
        self.destination_viewport.configure(nodes, "Destination · " + (rig.name if rig else "Choose a rig"))
        self.mapping_table.set_mapping(clip.mapping)
        counts = clip.mapping.summary() if clip.mapping else {}
        for status, badge in self.badges.items():
            badge.set_status("{} {}".format(counts.get(status.value, 0), status.value.title()), theme.status_color(status))
        report = self.controller.validate(self.clip_id)
        self.review_button.setEnabled(report.ok)
        headline = "{} errors · {} warnings".format(len(report.errors), len(report.warnings))
        detail = str((report.errors or report.warnings)[0]) if report.issues else "Mapping validated. Ready to review animation."
        self.validation_label.setText(headline + "  —  " + detail)
        self.validation_label.setToolTip("\n".join(str(issue) for issue in report.issues) or detail)
        self._highlight(self.mapping_table.selected_role())

    def _highlight(self, role):
        clip = self.controller.session.get_clip(self.clip_id)
        match = clip.mapping.matches.get(role) if clip and clip.mapping else None
        self.overlay.set_match(match)
        self.source_tree.highlight(match.source if match else None, theme.status_color(match.status) if match else theme.ACCENT)
        self.destination_tree.highlight(match.destination if match else None, theme.status_color(match.status) if match else theme.ACCENT)
        self._update_link()

    def _update_link(self):
        self.link_button.setEnabled(bool(self.mapping_table.selected_role() and
                                        self.source_tree.selected_joint() and self.destination_tree.selected_joint()))

    def _exclude(self, role, excluded):
        if self.clip_id:
            # Delay rebuilding the table until the checkbox signal has unwound.
            QtCore.QTimer.singleShot(0, lambda cid=self.clip_id, r=role, ex=excluded:
                                    self.controller.set_excluded(cid, r, ex))

    def link_selected(self):
        role = self.mapping_table.selected_role()
        source = self.source_tree.selected_joint()
        destination = self.destination_tree.selected_joint()
        if role and source and destination:
            self.controller.set_manual_match(self.clip_id, role, source, destination)
        else:
            self.controller.session.status("Select a role and one joint in each hierarchy.", "warning")

    def auto_match(self):
        if self.clip_id:
            self.controller.auto_map(self.clip_id)

    def reset_manual(self):
        if not self.clip_id:
            return
        answer = QtWidgets.QMessageBox.question(self, "Reset manual mapping?",
                    "Remove all manual corrections for this animation? Exclusions are kept.",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if answer == QtWidgets.QMessageBox.Yes:
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

    def dispose(self):
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
        self.release_viewports()

    def closeEvent(self, event):
        self.dispose()
        super().closeEvent(event)
