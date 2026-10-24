"""HumanIK-style definitions backed by the existing joint Mapping."""
from rigflow.core.session import SessionEvent
from rigflow.mapping.definition import joint_for, progress, slot_state
from rigflow.mapping.matcher import label_skeleton
from rigflow.skeleton.roles import REQUIRED_ROLES
from rigflow.ui import theme
from rigflow.ui.qt import QtCore, QtWidgets, Signal
from rigflow.ui.widgets.body_map import BodyMap, BODY_SLOTS, hand_slots


class MatchingView(QtWidgets.QWidget):
    back_requested = Signal()
    review_requested = Signal(str)
    session_event = Signal(object, object)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.clip_id = None
        self.side = "source"
        self.waiting = None
        self._active = False
        self._last_selection = ()
        self._labels = {}
        self.setObjectName("page")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 4, 24, 16)
        layout.setSpacing(10)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(theme.label("Character definition", heading=True))
        top.addStretch()
        self.model_buttons = {}
        self.model_group = QtWidgets.QButtonGroup(self)
        for side in ("source", "destination"):
            button = theme.button("", "Define this model in the main Maya viewport.", lambda s=side: self.set_side(s))
            button.setCheckable(True)
            self.model_group.addButton(button)
            self.model_buttons[side] = button
            top.addWidget(button)
        layout.addLayout(top)
        layout.addWidget(theme.label("Click a slot, then select its joint in Maya. Right-click to clear. Esc cancels.", muted=True))
        toolbar = QtWidgets.QHBoxLayout()
        self.auto_button = theme.button("Auto-detect", "Detect joints; keep manual definitions.", self.auto_detect)
        self.clear_button = theme.button("Clear all", "Clear the active model's definition.", self.clear_all)
        toolbar.addWidget(self.auto_button)
        toolbar.addWidget(self.clear_button)
        self.menu_button = theme.button("…", "Mapping presets")
        self.menu_button.setFixedWidth(48)
        self.menu_button.setStyleSheet("QPushButton::menu-indicator { image: none; width: 0; }")
        self.preset_menu = QtWidgets.QMenu(self)
        self.preset_menu.addAction("Load preset…", self.load_preset)
        self.preset_menu.addAction("Save preset…", self.save_preset)
        self.menu_button.setMenu(self.preset_menu)
        toolbar.addWidget(self.menu_button)
        toolbar.addStretch()
        self.display_buttons = {}
        self.display_group = QtWidgets.QButtonGroup(self)
        self.display = "Both"
        for display in ("Bones", "Mesh", "Both"):
            button = theme.button(display, "Display in the main Maya viewport.", lambda d=display: self.set_display(d))
            button.setCheckable(True)
            self.display_group.addButton(button)
            self.display_buttons[display] = button
            toolbar.addWidget(button)
        self.display_buttons["Both"].setChecked(True)
        layout.addLayout(toolbar)
        card = QtWidgets.QFrame()
        card.setObjectName("sectionCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(0)
        tabs = QtWidgets.QHBoxLayout()
        self.map_tabs = QtWidgets.QTabBar()
        self.map_tabs.addTab("Body")
        self.map_tabs.addTab("Hands")
        self.map_tabs.setExpanding(False)
        self.map_tabs.currentChanged.connect(lambda index: self.body_map.set_hands(index == 1))
        tabs.addWidget(self.map_tabs)
        tabs.addStretch()
        legend = theme.label('<span style="color:#58b368">●</span> Assigned &nbsp; '
                             '<span style="color:#e0b84c">●</span> Review &nbsp; '
                             '<span style="color:#d9534f">◯</span> Required &nbsp; · Optional', muted=True)
        legend.setToolTip("Green: assigned · Yellow: review automatic guess · Red outline: required and empty\nSmaller gray slots are optional. Hover a slot for its joint name.")
        tabs.addWidget(legend)
        card_layout.addLayout(tabs)
        self.body_map = BodyMap()
        self.body_map.slot_clicked.connect(self.click_slot)
        self.body_map.slot_menu.connect(self.slot_menu)
        card_layout.addWidget(self.body_map, 1)
        layout.addWidget(card, 1)
        self.status_line = theme.label("")
        self.status_line.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.status_line.setMinimumHeight(20)
        layout.addWidget(self.status_line)
        footer = QtWidgets.QHBoxLayout()
        self.back_button = theme.button("Back", "Return to Setup.", self.back_requested.emit)
        self.review_button = theme.button("Transfer", "Continue when both definitions are complete.", self.review, primary=True)
        footer.addWidget(self.back_button)
        footer.addStretch()
        footer.addWidget(self.review_button)
        layout.addLayout(footer)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.poll_selection)
        self.session_event.connect(self._event)
        self._unsubscribe = controller.session.subscribe(self.session_event.emit)
        self.setStyleSheet("QPushButton:checked { background: #354b52; border-color: #23b7db; }"
                           "QTabBar::tab { background: transparent; color: #a0a0a0; padding: 5px 16px; }"
                           "QTabBar::tab:selected { color: #23b7db; border-bottom: 2px solid #23b7db; }")

    def _event(self, event, payload):
        if event in (SessionEvent.RIG_CHANGED, SessionEvent.CLIPS_CHANGED):
            self.refresh()
        elif event == SessionEvent.STATUS and self._active:
            self.status_line.setText((payload or {}).get("message", ""))
            self.status_line.setToolTip(self.status_line.text())

    def set_clip(self, clip_id):
        self.clip_id = clip_id
        self.side = "source"
        self.display = "Both"
        self.display_buttons["Both"].setChecked(True)
        self.map_tabs.setCurrentIndex(0)
        self.cancel_waiting()

    def activate(self):
        self._active = True
        QtWidgets.QApplication.instance().installEventFilter(self)
        self._last_selection = tuple(self.controller.scene_selection())
        self.controller.show_definition_model(self.clip_id, self.side, self.display)
        self.timer.start()
        self.refresh()

    def eventFilter(self, watched, event):
        if self._active and self.waiting and event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
            self.cancel_waiting()
            return True
        return super().eventFilter(watched, event)

    def set_side(self, side):
        if self.side != side:
            self.cancel_waiting()
            self.side = side
            self._last_selection = tuple(self.controller.scene_selection())
            if self._active:
                self.controller.show_definition_model(self.clip_id, side, self.display)
        self.refresh()

    def set_display(self, display):
        self.display = display
        self.display_buttons[display].setChecked(True)
        if self._active:
            self.controller.show_definition_model(self.clip_id, self.side, display)

    def _mapping(self):
        clip = self.controller.session.get_clip(self.clip_id)
        return clip.mapping if clip else None

    def _selected_joint(self, selection):
        if len(selection) == 1:
            return self.controller.definition_joint(self.clip_id, self.side, selection[0])

    def click_slot(self, role):
        if not self._active or not self._mapping():
            return
        if self.waiting == role:
            self.cancel_waiting()
            return
        self.cancel_waiting()
        selection = tuple(self.controller.scene_selection())
        selected = self._selected_joint(selection)
        assigned = joint_for(self._mapping(), role, self.side)
        if selected and selected != assigned:
            self.controller.set_definition(self.clip_id, role, self.side, selected)
        elif assigned:
            self.controller.select_definition_joint(assigned)
        else:
            self.waiting = role
            self.body_map.waiting = role
            self._last_selection = selection
            self.body_map.update()
            self.status_line.setText("Select {} on {} in Maya · Esc cancels".format(role, self.controller.definition_label(self.side)))
        if selection and not selected:
            self._warn_selection(selection)

    def _warn_selection(self, selection):
        other = "destination" if self.side == "source" else "source"
        if any(self.controller.definition_joint(self.clip_id, other, node) for node in selection):
            message = "That joint belongs to {}. Choose a joint from {}.".format(self.controller.definition_label(other), self.controller.definition_label(self.side))
        else:
            message = "Select exactly one joint from {}.".format(self.controller.definition_label(self.side))
        self.controller.session.status(message, "warning")

    def poll_selection(self):
        if not self._active:
            return
        selection = tuple(self.controller.scene_selection())
        if selection == self._last_selection:
            return
        self._last_selection = selection
        if self.waiting and selection:
            joint = self._selected_joint(selection)
            if joint:
                role = self.waiting
                self.cancel_waiting()
                self.controller.set_definition(self.clip_id, role, self.side, joint)
            else:
                self._warn_selection(selection)

    def cancel_waiting(self):
        self.waiting = None
        self.body_map.waiting = None
        self.body_map.update()
        self.refresh()

    def clear_slot(self, role):
        self.cancel_waiting()
        self.controller.set_definition(self.clip_id, role, self.side, None)

    def slot_menu(self, role, position):
        menu = QtWidgets.QMenu(self)
        joint = joint_for(self._mapping(), role, self.side)
        menu.addAction("Clear", lambda: self.clear_slot(role)).setEnabled(bool(joint))
        menu.addAction("Select in scene", lambda: self.controller.select_definition_joint(joint)).setEnabled(bool(joint))
        menu.exec_(position)

    def clear_all(self):
        self.cancel_waiting()
        label = self.controller.definition_label(self.side)
        if QtWidgets.QMessageBox.question(self, "Clear definition?", "Clear all slots on {}?".format(label),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
            self.cancel_waiting()
            self.controller.clear_definition(self.clip_id, self.side)

    def auto_detect(self):
        self.cancel_waiting()
        self.controller.auto_map(self.clip_id)

    def refresh(self):
        mapping = self._mapping()
        counts = {}
        for side, button in self.model_buttons.items():
            skeleton = self.controller.definition_skeleton(self.clip_id, side)
            counts[side] = progress(mapping, side, skeleton)
            button.setText("{}  {}/{}".format(self.controller.definition_label(side), counts[side], len(REQUIRED_ROLES)))
            button.setChecked(side == self.side)
        skeleton = self.controller.definition_skeleton(self.clip_id, self.side)
        if skeleton is not None and self._labels.get(self.side, (None,))[0] is not skeleton:
            self._labels[self.side] = (skeleton, label_skeleton(skeleton))
        labeling = self._labels.get(self.side, (None, None))[1]
        roles = set(BODY_SLOTS) | set(hand_slots())
        self.body_map.states = {role: slot_state(mapping, role, self.side, skeleton or (), labeling) for role in roles}
        self.body_map.joints = {role: joint_for(mapping, role, self.side) for role in roles}
        self.body_map.update()
        report = self.controller.validate(self.clip_id)
        complete = all(count == len(REQUIRED_ROLES) for count in counts.values())
        self.review_button.setEnabled(complete and report.ok)
        if not self.waiting:
            text = " · ".join("{} {}/{}".format(self.controller.definition_label(s), counts[s], len(REQUIRED_ROLES)) for s in ("source", "destination"))
            missing = next(((s, r) for s in ("source", "destination") for r in REQUIRED_ROLES if not joint_for(mapping, r, s)), None)
            if missing:
                text += " — connect {} on {}".format(missing[1], self.controller.definition_label(missing[0]))
            elif report.errors:
                text += " — " + str(report.errors[0])
            else:
                text += " — Ready to transfer"
            self.status_line.setText(text)
        self.status_line.setToolTip("\n".join(str(i) for i in report.issues) or self.status_line.text())

    def review(self):
        if self.clip_id and self.review_button.isEnabled() and self.controller.validate(self.clip_id).ok:
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
                self.cancel_waiting()
                self.controller.load_preset(self.clip_id, path)

    def deactivate(self):
        self.timer.stop()
        self._active = False
        QtWidgets.QApplication.instance().removeEventFilter(self)
        self.cancel_waiting()
        self.controller.restore_definition_viewport()

    def hideEvent(self, event):
        self.deactivate()
        super().hideEvent(event)

    def dispose(self):
        self.deactivate()
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def closeEvent(self, event):
        self.dispose()
        super().closeEvent(event)
