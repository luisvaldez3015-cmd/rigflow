from __future__ import annotations

from rigflow.core.session import SessionEvent
from rigflow.ui.qt import QtCore, QtWidgets, Signal
from rigflow.ui import theme
from rigflow.ui.widgets.viewport_panel import ViewportPanel
from rigflow.ui.widgets.section_card import SectionCard


class ReviewView(QtWidgets.QWidget):
    """Lightweight playback review. Confirm is the only action here that bakes."""
    back_requested = Signal(str)
    confirmed = Signal(str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.controller = controller
        self.clip_id = None
        self._range = (1.0, 1.0)
        self._preview_ready = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        header = QtWidgets.QHBoxLayout()
        self.back_button = theme.button("‹ Back to mapping", "Stop the live preview and return to joint matching.", self.back)
        header.addWidget(self.back_button)
        header.addWidget(theme.label("Review animation", heading=True))
        header.addStretch()
        layout.addLayout(header)
        identities = QtWidgets.QHBoxLayout()
        self.source_label = theme.label("Source", muted=True)
        self.destination_label = theme.label("Destination", muted=True)
        identities.addWidget(self.source_label)
        identities.addStretch()
        identities.addWidget(self.destination_label)
        layout.addLayout(identities)
        self.viewport = ViewportPanel("Animation preview", controller, "destination")
        layout.addWidget(self.viewport, 1)
        self.preview_status = theme.label("Preparing preview…", muted=True)
        layout.addWidget(self.preview_status)
        controls = QtWidgets.QHBoxLayout()
        self.play_button = theme.button("▶ Play", "Play the timeline in this clip's frame range.", self.play)
        self.pause_button = theme.button("Pause", "Pause the timeline at the current frame.", self.pause)
        self.stop_button = theme.button("■ Stop", "Pause and return to the first frame.", self.stop)
        for widget in (self.play_button, self.pause_button, self.stop_button):
            controls.addWidget(widget)
        self.loop = QtWidgets.QCheckBox("Loop")
        self.loop.setToolTip("Repeat playback when the end of this clip is reached.")
        self.loop.setChecked(True)
        self.loop.toggled.connect(controller.set_loop)
        controls.addWidget(self.loop)
        controls.addStretch()
        controls.addWidget(theme.label("Frame", muted=True))
        self.frame_spin = QtWidgets.QDoubleSpinBox()
        self.frame_spin.setDecimals(2)
        self.frame_spin.setFixedWidth(100)
        self.frame_spin.setToolTip("Set the current timeline frame; fractional frames are supported.")
        controls.addWidget(self.frame_spin)
        layout.addLayout(controls)
        timeline = QtWidgets.QHBoxLayout()
        self.start_label = theme.label("1", muted=True)
        self.end_label = theme.label("120", muted=True)
        self.frame_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.frame_slider.setToolTip("Scrub the animation within its source frame range.")
        timeline.addWidget(self.start_label)
        timeline.addWidget(self.frame_slider, 1)
        timeline.addWidget(self.end_label)
        layout.addLayout(timeline)
        self.warning_card = SectionCard("Mapping notes")
        self.warnings = QtWidgets.QListWidget()
        self.warnings.setMinimumHeight(64)
        self.warnings.setMaximumHeight(110)
        self.warning_card.body.addWidget(self.warnings)
        layout.addWidget(self.warning_card)
        footer = QtWidgets.QHBoxLayout()
        self.layer = QtWidgets.QCheckBox("Bake to animation layer")
        self.layer.setChecked(True)
        self.layer.setToolTip("Write transferred keys to RigFlow's destination animation layer.")
        footer.addWidget(self.layer)
        footer.addStretch()
        self.confirm_button = theme.button("Confirm / Add Animation", "Bake this animation onto the destination, then return to your clip list.", self.confirm, True)
        footer.addWidget(self.confirm_button)
        layout.addLayout(footer)
        self.frame_slider.valueChanged.connect(lambda value: self._set_frame(value / 100.0))
        self.frame_spin.valueChanged.connect(self._set_frame)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._poll)
        self._unsubscribe = controller.session.subscribe(self._event)

    def _event(self, event, payload):
        if event in (SessionEvent.CLIPS_CHANGED, SessionEvent.RIG_CHANGED) and self.clip_id:
            report = self.controller.validate(self.clip_id)
            self.confirm_button.setEnabled(report.ok)
            self._show_warnings(report)

    def set_clip(self, clip_id):
        self.deactivate()
        self.clip_id = clip_id
        self.controller.session.set_active_clip(clip_id)
        clip = self.controller.session.get_clip(clip_id)
        if clip is None:
            return False
        self._range = self.controller.frame_range(clip_id) or clip.frame_range
        start, end = self._range
        self.start_label.setText("{:g}".format(start))
        self.end_label.setText("{:g}".format(end))
        self.frame_slider.blockSignals(True)
        self.frame_spin.blockSignals(True)
        self.frame_slider.setRange(round(start * 100), round(end * 100))
        self.frame_spin.setRange(start, end)
        self.frame_slider.setValue(round(start * 100))
        self.frame_spin.setValue(start)
        self.frame_slider.blockSignals(False)
        self.frame_spin.blockSignals(False)
        rig = self.controller.session.rig
        self.source_label.setText("Source · {} · {}".format(clip.name, clip.convention))
        self.destination_label.setText("Destination · " + (rig.name if rig else "Not selected"))
        nodes = self.controller.viewport_nodes(clip_id) + self.controller.viewport_nodes(clip_id, destination=True)
        self.viewport.configure(nodes, "Review · {} → {}".format(clip.name, rig.name if rig else "Destination"))
        report = self.controller.validate(clip_id)
        self._show_warnings(report)
        self.confirm_button.setEnabled(report.ok)
        self._preview_ready = bool(report.ok and self.controller.start_preview(clip_id))
        for widget in (self.play_button, self.pause_button, self.stop_button, self.frame_slider, self.frame_spin, self.loop):
            widget.setEnabled(self._preview_ready)
        self.preview_status.setText(self.controller.preview_message(clip_id) if self._preview_ready else
                                   "Live preview unavailable. Check the status message below; transfer will retry the backend.")
        if self._preview_ready:
            self.controller.set_loop(self.loop.isChecked())
            self.controller.set_frame(start)
            self.timer.start()
        return True

    def _show_warnings(self, report):
        self.warnings.clear()
        for issue in report.issues:
            self.warnings.addItem(str(issue))
        if not report.issues:
            self.warnings.addItem("Mapping validated. All required roles are linked.")

    def _sync_frame(self, frame):
        self.frame_slider.blockSignals(True)
        self.frame_spin.blockSignals(True)
        self.frame_slider.setValue(round(frame * 100))
        self.frame_spin.setValue(frame)
        self.frame_slider.blockSignals(False)
        self.frame_spin.blockSignals(False)

    def _set_frame(self, frame):
        if self.clip_id and self._preview_ready:
            self.controller.set_frame(frame)
            self._sync_frame(frame)

    def _poll(self):
        if self._preview_ready:
            frame = self.controller.current_frame()
            if frame is not None:
                self._sync_frame(frame)
            self.play_button.setText("Playing…" if self.controller.is_playing() else "▶ Play")

    def play(self):
        if self._preview_ready:
            self.controller.play()

    def pause(self):
        if self._preview_ready:
            self.controller.pause()

    def stop(self):
        self.pause()
        self._set_frame(self._range[0])

    def back(self):
        clip_id = self.clip_id
        self.deactivate()
        if clip_id:
            self.back_requested.emit(clip_id)

    def confirm(self):
        if self.clip_id and self.controller.validate(self.clip_id).ok:
            self.pause()
            result = self.controller.bake(self.clip_id, to_layer=self.layer.isChecked())
            if result is not None:
                clip_id = self.clip_id
                self.deactivate()
                self.confirmed.emit(clip_id)

    def deactivate(self):
        self.timer.stop()
        if self.clip_id and self._preview_ready:
            self.controller.stop_preview(self.clip_id)
        self._preview_ready = False
        self.viewport.release()

    def dispose(self):
        self.deactivate()
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def closeEvent(self, event):
        self.dispose()
        super().closeEvent(event)
