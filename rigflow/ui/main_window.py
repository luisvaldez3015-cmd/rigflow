from pathlib import Path

from rigflow.core import config
from rigflow.core.session import SessionEvent
from rigflow.ui.qt import QtGui, QtWidgets, Signal, maya_main_window, ensure_application_fonts
from rigflow.ui import theme
from rigflow.ui.help_menu import add_help_menu
from rigflow.ui.setup_view import SetupView
from rigflow.ui.matching_view import MatchingView
from rigflow.ui.review_view import ReviewView
from rigflow.ui.rig_view import RigView
from rigflow.ui.widgets.logo import LogoWidget
from rigflow.ui.widgets.step_indicator import StepIndicator
from rigflow.ui.widgets.drop_area import FILE_FILTER
from rigflow.ui.widgets.status_badge import StatusBadge
from rigflow.ui.widgets.progress_banner import ProgressBanner

try:
    if maya_main_window() is None:
        raise ImportError
    from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
except ImportError:
    class MayaQWidgetDockableMixin:
        """Standalone fallback for offscreen previews."""


class MainWindow(MayaQWidgetDockableMixin, QtWidgets.QMainWindow):
    """Plan-driven pages with explicitly owned preview resources."""
    session_event = Signal(object, object)

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        ensure_application_fonts()
        if controller is None:
            from rigflow.ui.controller import Controller
            controller = Controller()
        self.controller, self.session = controller, controller.session
        self._disposed = False
        self._validated_clip = None
        self.setObjectName(config.WINDOW_OBJECT_NAME)
        self.setWindowTitle(config.TOOL_TITLE)
        self.setWindowIcon(QtGui.QIcon(str(Path(__file__).resolve().parents[2] / "assets/icons/rigflow_window.png")))
        self.setMinimumSize(960, 640)
        self.resize(1160, 900)
        self.setStyleSheet(theme.stylesheet())
        central = QtWidgets.QWidget()
        central.setObjectName("page")
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.progress_banner = ProgressBanner()
        outer.addWidget(self.progress_banner)
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(24, 16, 24, 16)
        self.logo = LogoWidget()
        header.addWidget(self.logo)
        header.addStretch()
        self.stepper = StepIndicator()
        self.stepper.step_requested.connect(self._navigate_step)
        header.addWidget(self.stepper)
        outer.addLayout(header)
        self.stack = QtWidgets.QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.setup_view = SetupView(self)
        self.match_view = MatchingView(controller)
        self.transfer_view = ReviewView(controller)
        self.rig_view = RigView(controller)
        for page in (self.setup_view, self.rig_view, self.match_view, self.transfer_view):
            self.stack.addWidget(page)
        # Preserve shelf scripts that use the previous navigation names.
        self.main_page, self.matching_view, self.review_view = self.setup_view, self.match_view, self.transfer_view
        self.rig_view.back_requested.connect(self.show_setup)
        self.rig_view.bound.connect(self._continue_plan)
        self.match_view.back_requested.connect(self.show_setup)
        self.match_view.review_requested.connect(self.open_transfer)
        self.transfer_view.back_requested.connect(self.open_match)
        self.transfer_view.done_requested.connect(self.show_setup)
        self.transfer_view.new_requested.connect(self.new_animation)
        self.add_menu = QtWidgets.QMenu(self)
        self.add_menu.addAction("From file…", self.add_file)
        self.add_menu.addAction("Use Maya selection", controller.add_model_from_selection)
        self.add_menu.addAction("From scene…", self.add_from_scene)
        self.statusBar().showMessage("Add your models. RigFlow detects their mesh, rig and animation.")
        self.status_badge = StatusBadge("Ready", theme.GRAY)
        self.statusBar().addPermanentWidget(self.status_badge)
        self.help_menu = add_help_menu(self, controller)
        self.session_event.connect(self._event)
        self._unsubscribe = self.session.subscribe(self.session_event.emit)
        controller.operation_started.connect(self._busy)
        controller.operation_finished.connect(self._idle)
        self.refresh()

    def _event(self, event, payload):
        if event == SessionEvent.STATUS:
            data = payload or {}
            level = data.get("level", "info")
            self.statusBar().showMessage(data.get("message", ""))
            self.status_badge.set_status(level.title(), dict(error=theme.RED, warning=theme.YELLOW, success=theme.GREEN, info=theme.ACCENT).get(level, theme.GRAY))
        elif event in (SessionEvent.MODEL_CHANGED, SessionEvent.RIG_CHANGED, SessionEvent.CLIPS_CHANGED, SessionEvent.ACTIVE_CLIP_CHANGED, SessionEvent.CHARACTERS_CHANGED, SessionEvent.PLAN_CHANGED):
            clip = self.session.active_clip
            if event == SessionEvent.RIG_CHANGED or not clip or clip.clip_id != self._validated_clip:
                self._validated_clip = None
                self.setup_view.validation_label.clear()
            self.refresh()
            current = self.stack.currentWidget()
            if current in (self.match_view, self.transfer_view) and current.clip_id and not self.session.get_clip(current.clip_id):
                self.show_setup()

    def refresh(self):
        self.setup_view.refresh()
        self._update_stepper()

    def _update_stepper(self):
        # Match owns one contextual status line; avoid a second, stale readout.
        self.statusBar().setVisible(self.stack.currentWidget() is not self.match_view)
        names = (self.session.started_steps if self.stack.currentWidget() is not self.setup_view
                 and self.session.started_steps else self.session.plan.steps)
        self.stepper.set_steps(names)
        page_name = {self.setup_view: "Setup", self.rig_view: "Rig", self.match_view: "Match", self.transfer_view: "Transfer"}[self.stack.currentWidget()]
        current = names.index(page_name) + 1 if page_name in names else 1
        clip = self.session.active_clip
        allowed, completed = [1], []
        if self.controller.rig_fit() is not None and "Rig" in names:
            allowed.append(names.index("Rig") + 1)
        if clip and self.session.destination_ready and "Match" in names:
            allowed.append(names.index("Match") + 1)
            if self.controller.validate(clip.clip_id).ok and "Transfer" in names:
                allowed.append(names.index("Transfer") + 1)
        completed = list(range(1, current))
        if clip and clip.status.value == "transferred" and "Transfer" in names:
            completed.append(names.index("Transfer") + 1)
        self.stepper.set_state(current, allowed, completed)

    def _navigate_step(self, step):
        name = self.stepper.names[step - 1]
        if name == "Setup":
            self.show_setup()
        elif name == "Rig":
            self.open_rig()
        elif self.session.active_clip:
            (self.open_match if name == "Match" else self.open_transfer)(self.session.active_clip_id)

    def show_add_menu(self):
        tile = self.setup_view.small_add_tile if self.session.characters else self.setup_view.add_tile
        self.add_menu.popup(tile.mapToGlobal(tile.rect().bottomLeft()))

    def add_path(self, path):
        return self.controller.add_model_from_file(path)

    def add_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Add a model", "", FILE_FILTER)
        if path:
            self.add_path(path)

    def add_from_scene(self):
        roots = self.controller.list_scene_candidates()
        if not roots:
            self.session.status("No unassigned scene models found. Add a model from a file or Maya selection.", "warning")
            return
        root, accepted = QtWidgets.QInputDialog.getItem(self, "Model from scene", "Mesh or skeleton root", roots, 0, False)
        if accepted:
            self.controller.add_model_from_scene(root)

    def replace_model(self, character_id):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Replace model", "", FILE_FILTER)
        if path:
            return self.controller.replace_model_from_file(character_id, path)

    def start_plan(self, kind=None):
        result = self.controller.start_plan(kind)
        if result:
            self._continue_plan(result)
        return result

    def _continue_plan(self, result):
        if result["step"] == "rig":
            self.open_rig()
        elif result["step"] == "match":
            self.open_match(result["clip_id"])
        else:
            self.show_setup()

    def open_rig(self):
        if self.controller.rig_fit() is None:
            return
        self.stack.setCurrentWidget(self.setup_view)
        self.match_view.deactivate()
        self.transfer_view.deactivate()
        self.rig_view.set_fit(self.controller.rig_fit())
        self.stack.setCurrentWidget(self.rig_view)
        self.rig_view.activate()
        self._update_stepper()

    def replace_clip(self, clip_id):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Replace source animation", "", FILE_FILTER)
        if path:
            self._validated_clip = None
            self.controller.replace_animation(clip_id, path)

    def validate_active(self):
        clip = self.session.active_clip
        if clip is None:
            message, color, report = "Add an animation first", theme.YELLOW, None
        else:
            if clip.mapping is None and self.session.destination_ready:
                self.controller.auto_map(clip.clip_id)
            report = self.controller.validate(clip.clip_id)
            if report.errors:
                hint = "Use selection or Browse in Rig." if not self.session.destination_ready else "Open Match to review the highlighted roles."
                message, color = str(report.errors[0]) + " " + hint, theme.RED
            elif report.warnings:
                message, color = "{} to review".format(len(report.warnings)), theme.YELLOW
            else:
                message, color = "Ready: {} roles matched".format(len(clip.mapping.complete_pairs())), theme.GREEN
        self._validated_clip = clip.clip_id if clip and self.session.destination_ready else None
        self.refresh()
        self.setup_view.validation_label.setText(message)
        self.setup_view.validation_label.setStyleSheet("color: %s;" % color)
        self.setup_view.validation_label.setToolTip("\n".join(str(issue) for issue in report.issues) if report else message)
        self.session.status(message, "error" if color == theme.RED else "warning" if color == theme.YELLOW else "success")
        return report

    def open_match(self, clip_id):
        if not self.session.get_clip(clip_id):
            return
        # Hide first: preview cleanup emits session events synchronously.
        self.stack.setCurrentWidget(self.setup_view)
        self.transfer_view.deactivate()
        self.match_view.deactivate()
        self.rig_view.deactivate()
        self.match_view.set_clip(clip_id)
        self._validated_clip = clip_id if self.session.destination_ready else None
        self.stack.setCurrentWidget(self.match_view)
        self.match_view.activate()
        self._update_stepper()

    def open_transfer(self, clip_id):
        if not self.session.get_clip(clip_id):
            return
        report = self.controller.validate(clip_id)
        if not report.ok:
            self.open_match(clip_id)
            self.session.status(str(report.errors[0]), "error")
            return
        # Hide Match BEFORE preview events can trigger a viewport refresh.
        self.stack.setCurrentWidget(self.setup_view)
        self.match_view.deactivate()
        self.transfer_view.deactivate()
        self.rig_view.deactivate()
        self.session.set_active_clip(clip_id)
        self._validated_clip = clip_id
        self.stack.setCurrentWidget(self.transfer_view)
        if not self.transfer_view.set_clip(clip_id):
            self.show_setup()
        self._update_stepper()

    def show_setup(self):
        self.stack.setCurrentWidget(self.setup_view)
        self.match_view.deactivate()
        self.transfer_view.deactivate()
        self.rig_view.deactivate()
        self.refresh()

    def new_animation(self):
        source_id = self.session.plan.source_id
        self.show_setup()
        if source_id:
            self.replace_model(source_id)

    show_main = show_setup
    open_matching = open_match
    open_review = open_transfer
    transfer_clip = open_transfer

    def _busy(self, message):
        self._busy_message = message
        self.progress_banner.start(message)
        self.stack.setEnabled(False)
        self.stepper.setEnabled(False)
        self.menuBar().setEnabled(False)
        self.statusBar().showMessage(message)
        self.status_badge.set_status("Working", theme.ACCENT)

    def _idle(self):
        self.progress_banner.finish()
        self.stack.setEnabled(True)
        self.stepper.setEnabled(True)
        self.menuBar().setEnabled(True)
        if self.statusBar().currentMessage() == getattr(self, "_busy_message", None):
            self.statusBar().showMessage("Ready.")
            self.status_badge.set_status("Ready", theme.GRAY)

    def _dispose(self):
        if not self._disposed:
            self._disposed = True
            self._unsubscribe()
            self.match_view.dispose()
            self.transfer_view.dispose()
            self.rig_view.dispose()
            self.controller.shutdown()

    def dockCloseEventTriggered(self):
        self._dispose()

    def closeEvent(self, event):
        self._dispose()
        super().closeEvent(event)
