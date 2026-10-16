from __future__ import annotations

from rigflow.core import config
from rigflow.core.session import SessionEvent
from rigflow.skeleton.roles import REQUIRED_ROLES
from rigflow.ui.qt import QtCore, QtWidgets, Signal, maya_main_window, ensure_application_fonts
from rigflow.ui import theme
from rigflow.ui.help_menu import add_help_menu
from rigflow.ui.matching_view import MatchingView
from rigflow.ui.review_view import ReviewView
from rigflow.ui.widgets.section_card import SectionCard
from rigflow.ui.widgets.drop_area import DropArea, FILE_FILTER
from rigflow.ui.widgets.empty_state import EmptyState
from rigflow.ui.widgets.clip_list import ClipList
from rigflow.ui.widgets.status_badge import StatusBadge
from rigflow.ui.widgets.progress_banner import ProgressBanner

try:
    if maya_main_window() is None:
        raise ImportError
    from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
except ImportError:
    class MayaQWidgetDockableMixin:
        """Standalone fallback; Maya's mixin is used only in a live Maya UI."""


class MainWindow(MayaQWidgetDockableMixin, QtWidgets.QMainWindow):
    """Single destination with a persistent list of animation clips."""
    session_event = Signal(object, object)

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        ensure_application_fonts()
        if controller is None:
            from rigflow.ui.controller import Controller
            controller = Controller()
        self.controller = controller
        self.session = controller.session
        self._disposed = False
        self.setObjectName(config.WINDOW_OBJECT_NAME)
        self.setWindowTitle(config.TOOL_TITLE)
        self.setMinimumSize(960, 640)
        self.resize(1160, 900)
        self.setStyleSheet(theme.stylesheet())
        central = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.progress_banner = ProgressBanner()
        outer.addWidget(self.progress_banner)
        self.stack = QtWidgets.QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.main_page = self._build_main()
        self.matching_view = MatchingView(controller)
        self.review_view = ReviewView(controller)
        for page in (self.main_page, self.matching_view, self.review_view):
            self.stack.addWidget(page)
        self.matching_view.back_requested.connect(self.show_main)
        self.matching_view.review_requested.connect(self.open_review)
        self.review_view.back_requested.connect(self.open_matching)
        self.review_view.confirmed.connect(lambda _: self.show_main())
        self.clip_list.map_requested.connect(self.open_matching)
        self.clip_list.review_requested.connect(self.open_review)
        self.clip_list.transfer_requested.connect(self.transfer_clip)
        self.clip_list.remove_requested.connect(self.controller.remove_clip)
        self.clip_list.replace_requested.connect(self.replace_clip)
        self.clip_list.add_requested.connect(self.add_file)
        self.statusBar().showMessage("Welcome to RigFlow. Choose your destination, then add an animation.")
        self.status_badge = StatusBadge("Ready", theme.GRAY)
        self.statusBar().addPermanentWidget(self.status_badge)
        self.help_menu = add_help_menu(self, controller)
        self.session_event.connect(self._event)
        self._unsubscribe = self.session.subscribe(self.session_event.emit)
        controller.operation_started.connect(self._busy)
        controller.operation_finished.connect(self._idle)
        self.refresh()

    def _build_main(self):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        page = QtWidgets.QWidget()
        page.setObjectName("page")
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(12)
        brand_row = QtWidgets.QHBoxLayout()
        brand = theme.label("RigFlow")
        brand.setObjectName("brand")
        brand_row.addWidget(brand)
        brand_row.addStretch()
        step = theme.label("01  IMPORT     /     02  MATCH     /     03  TRANSFER")
        step.setObjectName("step")
        brand_row.addWidget(step)
        layout.addLayout(brand_row)
        layout.addWidget(theme.label("A new performance. Your character.", muted=True))
        self.model_section = SectionCard("A   Model", "The destination character's geometry")
        self.model_section.add_action(theme.button("Use selection", "Inspect the selected Maya mesh transforms.", self.controller.set_model_from_selection))
        self.model_badge = StatusBadge("Not loaded", theme.GRAY)
        self.model_section.add_action(self.model_badge)
        self.model_empty = EmptyState("No model loaded. Import a character or use your Maya selection.", glyph="◇")
        self.model_details = theme.label("")
        self.model_details.setWordWrap(True)
        self.model_section.body.addWidget(self.model_empty)
        self.model_section.body.addWidget(self.model_details)
        self.model_drop = DropArea("Drop destination geometry · .fbx / .ma / .mb")
        self.model_drop.file_selected.connect(self.controller.import_model)
        self.model_section.body.addWidget(self.model_drop)
        layout.addWidget(self.model_section)
        self.rig_section = SectionCard("B   Rig", "The destination skeleton — any naming convention")
        self.rig_section.add_action(theme.button("Use selection", "Read the selected skeleton root, or the rig driving a selected skinned mesh.", self.controller.set_rig_from_selection))
        self.rig_badge = StatusBadge("Not loaded", theme.GRAY)
        self.rig_section.add_action(self.rig_badge)
        self.rig_empty = EmptyState("No rig loaded. Choose the skeleton that will receive the animation.", glyph="⑂")
        self.rig_details = theme.label("")
        self.rig_details.setWordWrap(True)
        self.rig_section.body.addWidget(self.rig_empty)
        self.rig_section.body.addWidget(self.rig_details)
        self.rig_drop = DropArea("Drop destination rig · .fbx / .ma / .mb")
        self.rig_drop.file_selected.connect(self.controller.import_rig)
        self.rig_section.body.addWidget(self.rig_drop)
        layout.addWidget(self.rig_section)
        self.animation_section = SectionCard("C   Animation", "Add a performance, review its mapping, then transfer")
        self.animation_section.add_action(theme.button("From scene…", "Pick an animated source skeleton root from the current Maya scene.", self.add_from_scene))
        self.animation_section.add_action(theme.button("Add Animation", "Import an animation file and open the matching workspace.", self.add_file, True))
        self.clip_list = ClipList()
        self.animation_section.body.addWidget(self.clip_list)
        layout.addWidget(self.animation_section, 1)
        self.footer_hint = theme.label("Geometry is optional. A destination rig is required before matching and transfer.", muted=True)
        layout.addWidget(self.footer_hint)
        layout.addStretch()
        scroll.setWidget(page)
        for drop in (self.model_drop, self.rig_drop):
            drop.rejected.connect(lambda message: self.session.status(message, "warning"))
        return scroll

    def _event(self, event, payload):
        if event == SessionEvent.STATUS:
            data = payload or {}
            level = data.get("level", "info")
            self.statusBar().showMessage(data.get("message", ""))
            colors = dict(error=theme.RED, warning=theme.YELLOW, success=theme.GREEN, info=theme.ACCENT)
            self.status_badge.set_status(level.title(), colors.get(level, theme.GRAY))
        elif event in (SessionEvent.MODEL_CHANGED, SessionEvent.RIG_CHANGED, SessionEvent.CLIPS_CHANGED):
            self.refresh()
            clip_id = self.review_view.clip_id if self.stack.currentWidget() == self.review_view else self.matching_view.clip_id
            if self.stack.currentWidget() != self.main_page and clip_id and self.session.get_clip(clip_id) is None:
                self.show_main()

    def refresh(self):
        model, rig = self.session.model, self.session.rig
        self.model_empty.setVisible(model is None)
        self.model_details.setVisible(model is not None)
        if model:
            self.model_details.setText("{}\n{} meshes  ·  {:,} vertices  ·  {}\n{}".format(
                model.name, len(model.meshes), model.vertex_count,
                "Skinned" if model.skinned else "Unskinned", model.message))
            self.model_badge.set_status("Detected" if model.valid else "No mesh detected", theme.GREEN if model.valid else theme.YELLOW)
        else:
            self.model_badge.set_status("Not loaded", theme.GRAY)
        self.rig_empty.setVisible(rig is None)
        self.rig_details.setVisible(rig is not None)
        if rig:
            found = set(rig.labeling.roles()) if rig.labeling else set()
            missing = [role for role in REQUIRED_ROLES if role not in found]
            details = "Root: {}  ·  {} joints  ·  Detected: {}\n{} / {} required roles found".format(
                rig.root, rig.joint_count, rig.convention, len(REQUIRED_ROLES) - len(missing), len(REQUIRED_ROLES))
            if missing:
                details += "  ·  Missing: " + ", ".join(missing)
            if rig.message:
                details += "\n" + rig.message
            if rig.warnings:
                details += "\nWarning: " + rig.warnings[0]
            self.rig_details.setText(details)
            self.rig_details.setToolTip("\n".join(rig.warnings))
            self.rig_badge.set_status("Needs attention" if missing or not rig.valid else "Validated",
                                      theme.YELLOW if missing or not rig.valid else theme.GREEN)
        else:
            self.rig_badge.set_status("Not loaded", theme.GRAY)
        self.clip_list.set_clips(self.session.clips)

    def add_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Add source animation", "", FILE_FILTER)
        if path:
            clip = self.controller.add_animation_from_file(path)
            if clip:
                self.open_matching(clip.clip_id)

    def add_from_scene(self):
        roots = self.controller.list_scene_skeleton_roots()
        if not roots:
            self.session.status("No source skeleton roots found. Import an animated skeleton first.", "warning")
            return
        root, accepted = QtWidgets.QInputDialog.getItem(self, "Source from scene", "Animated skeleton root", roots, 0, False)
        if accepted:
            clip = self.controller.add_animation_from_scene(root)
            if clip:
                self.open_matching(clip.clip_id)

    def replace_clip(self, clip_id):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Replace source animation", "", FILE_FILTER)
        if path:
            replace = getattr(self.controller, "replace_animation", None)
            if replace is None:
                self.session.status("This controller does not support replacement.", "warning")
            else:
                clip = replace(clip_id, path)
                if clip:
                    self.open_matching(clip_id)

    def transfer_clip(self, clip_id):
        if self.controller.validate(clip_id).ok:
            self.controller.bake(clip_id, to_layer=True)
        else:
            self.open_matching(clip_id)
            self.session.status("Resolve mapping errors before transfer.", "warning")

    def open_matching(self, clip_id):
        if self.session.get_clip(clip_id) is None:
            return
        self.review_view.deactivate()
        self.matching_view.set_clip(clip_id)
        self.stack.setCurrentWidget(self.matching_view)

    def open_review(self, clip_id):
        report = self.controller.validate(clip_id)
        if not report.ok:
            self.open_matching(clip_id)
            self.session.status(str(report.errors[0]), "error")
            return
        # Hide the matching page *before* set_clip: starting the preview emits
        # session events that would otherwise re-embed its viewports while it is
        # still the visible page, leaking hidden panels and cameras.
        self.matching_view.release_viewports()
        self.stack.setCurrentWidget(self.review_view)
        if not self.review_view.set_clip(clip_id):
            self.show_main()

    def show_main(self):
        self.review_view.deactivate()
        self.matching_view.release_viewports()
        self.stack.setCurrentWidget(self.main_page)
        self.refresh()

    def _busy(self, message):
        self._busy_message = message
        self.progress_banner.start(message)
        self.stack.setEnabled(False)
        self.menuBar().setEnabled(False)
        self.statusBar().showMessage(message)
        self.status_badge.set_status("Working", theme.ACCENT)

    def _idle(self):
        self.progress_banner.finish()
        self.stack.setEnabled(True)
        self.menuBar().setEnabled(True)
        if self.statusBar().currentMessage() == getattr(self, "_busy_message", None):
            self.statusBar().showMessage("Ready.")
            self.status_badge.set_status("Ready", theme.GRAY)

    def _dispose(self):
        if not self._disposed:
            self._disposed = True
            self._unsubscribe()
            self.matching_view.dispose()
            self.review_view.dispose()
            self.controller.shutdown()

    def dockCloseEventTriggered(self):
        """Maya closes workspaceControls independently of QWidget.closeEvent."""
        self._dispose()

    def closeEvent(self, event):
        self._dispose()
        super().closeEvent(event)
