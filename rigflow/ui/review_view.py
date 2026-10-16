from __future__ import annotations

from rigflow.core.session import SessionEvent
from rigflow.ui.qt import QtCore, QtWidgets, Signal
from rigflow.ui import theme
from rigflow.ui.widgets.viewport_panel import ViewportPanel
from rigflow.ui.widgets.section_card import SectionCard


class ReviewView(QtWidgets.QWidget):
    """Step three: playback, transfer and a persistent result card."""
    back_requested = Signal(str)
    confirmed = Signal(str)
    done_requested = Signal()
    new_requested = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.controller = controller
        self.clip_id = None
        self._range = (1.0, 1.0)
        self._preview_ready = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 16)
        layout.setSpacing(12)
        self.title = theme.label("Transfer", heading=True)
        layout.addWidget(self.title)
        identities = QtWidgets.QHBoxLayout()
        self.source_label = theme.label("Source", muted=True)
        self.destination_label = theme.label("Destination", muted=True)
        identities.addWidget(self.source_label)
        identities.addStretch()
        identities.addWidget(self.destination_label)
        layout.addLayout(identities)
        content = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.LeftToRight)
        content.setSpacing(16)
        self.content_layout = content
        preview = QtWidgets.QVBoxLayout()
        preview.setSpacing(8)
        self.viewport = ViewportPanel("Animation preview", controller, "destination")
        preview.addWidget(self.viewport, 1)
        content.addLayout(preview, 1)
        self.actions_panel = QtWidgets.QWidget()
        self.actions_panel.setObjectName("page")
        side = QtWidgets.QVBoxLayout(self.actions_panel)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(12)
        self.actions_scroll = QtWidgets.QScrollArea()
        self.actions_scroll.setWidgetResizable(True)
        self.actions_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.actions_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.actions_scroll.setWidget(self.actions_panel)
        content.addWidget(self.actions_scroll)
        layout.addLayout(content, 1)
        self.preview_status = theme.label("Preparing preview…", muted=True)
        preview.addWidget(self.preview_status)
        controls = QtWidgets.QHBoxLayout()
        self.play_button = theme.button("Play", "Play the timeline in this clip's frame range.", self.play)
        self.pause_button = theme.button("Pause", "Pause the timeline at the current frame.", self.pause)
        self.stop_button = theme.button("Stop", "Pause and return to the first frame.", self.stop)
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
        preview.addLayout(controls)
        timeline = QtWidgets.QHBoxLayout()
        self.start_label = theme.label("1", muted=True)
        self.end_label = theme.label("120", muted=True)
        self.frame_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.frame_slider.setToolTip("Scrub the animation within its source frame range.")
        timeline.addWidget(self.start_label)
        timeline.addWidget(self.frame_slider, 1)
        timeline.addWidget(self.end_label)
        preview.addLayout(timeline)
        self.warning_card = SectionCard("Mapping notes")
        self.warnings = QtWidgets.QListWidget()
        self.warnings.setMinimumHeight(64)
        self.warnings.setMaximumHeight(110)
        self.warnings.setWordWrap(True)
        self.warnings.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.warning_card.setFixedHeight(168)
        self.warning_card.body.addWidget(self.warnings)
        side.addWidget(self.warning_card)
        self.layer = QtWidgets.QCheckBox("Bake to animation layer")
        self.layer.setChecked(True)
        self.layer.setToolTip("Write transferred keys to RigFlow's destination animation layer.")
        side.addWidget(self.layer)
        self.confirm_button = theme.button("Transfer", "Bake the animation onto the destination using the selected layer option.", self.confirm, True)
        self.transfer_button = self.confirm_button
        side.addWidget(self.confirm_button)
        self.result_card = SectionCard("Transfer complete")
        self.result_label = theme.label("")
        self.result_label.setWordWrap(True)
        self.result_card.body.addWidget(self.result_label)
        self.result_card.hide()
        side.addWidget(self.result_card)
        self.new_button = theme.button("New anim", "Stop preview, return to Setup and add the next animation.", self.new_requested.emit)
        side.addWidget(self.new_button)
        self.done_button = theme.button("Done", "Return to Setup with the transferred clip in the list.", self.done_requested.emit)
        side.addWidget(self.done_button)
        side.addStretch()
        footer = QtWidgets.QHBoxLayout()
        self.back_button = theme.button("‹ Back", "Stop the live preview and return to Match.", self.back)
        footer.addWidget(self.back_button)
        footer.addStretch()
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
            self._show_result()
            clip = self.controller.session.get_clip(self.clip_id)
            if clip and clip.status.value == "transferred":
                self._preview_ready = False
                self.timer.stop()
                self.confirm_button.setEnabled(False)
                self._enable_playback(False)
                self.preview_status.setText("Transferred. Keys are baked on the destination.")

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
        self.title.setText("Transfer · {} → {}".format(clip.name, rig.name if rig else "Destination"))
        self.source_label.setText("Source · {} · {}".format(clip.name, clip.convention))
        self.destination_label.setText("Destination · " + (rig.name if rig else "Not selected"))
        nodes = self.controller.viewport_nodes(clip_id) + self.controller.viewport_nodes(clip_id, destination=True)
        self.viewport.configure(nodes, "{} → {}".format(clip.name, rig.name if rig else "Destination"))
        self._show_result()
        report = self.controller.validate(clip_id)
        self._show_warnings(report)
        self.confirm_button.setEnabled(report.ok)
        self._preview_ready = bool(report.ok and self.controller.start_preview(clip_id))
        self._enable_playback(self._preview_ready)
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

    def _enable_playback(self, enabled):
        for widget in (self.play_button, self.pause_button, self.stop_button, self.frame_slider, self.frame_spin, self.loop):
            widget.setEnabled(enabled)

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
            self.play_button.setText("Playing…" if self.controller.is_playing() else "Play")

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
                self.timer.stop()
                self._preview_ready = False
                self.preview_status.setText("Transferred. Keys are baked on the destination.")
                self._show_result()
                self.confirmed.emit(self.clip_id)

    def _show_result(self):
        clip = self.controller.session.get_clip(self.clip_id)
        result = clip.result if clip else {}
        self.result_card.setVisible(bool(result))
        if result:
            verification = result.get("verification", {})
            self.result_label.setText("Backend: {}\nLayer: {}\nJoints baked: {}\nBone-length error: {:.6g}\nElapsed: {:.2f} s".format(
                result.get("backend", "—"), result.get("layer") or "Base animation",
                len(result.get("baked_joints", [])), verification.get("max_bone_length_error", 0),
                verification.get("elapsed_s", 0)))

    def resizeEvent(self, event):
        self.actions_scroll.setFixedWidth(248 if self.width() < 1080 else 270)
        super().resizeEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        self.viewport.release()
        super().hideEvent(event)

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
