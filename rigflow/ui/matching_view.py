"""HumanIK-style definitions backed by the existing joint Mapping."""
from rigflow.core.session import SessionEvent
from rigflow.mapping.definition import joint_for, progress, slot_state
from rigflow.mapping.matcher import label_skeleton
from rigflow.skeleton.roles import REQUIRED_ROLES, display_name
from rigflow.ui import theme
from rigflow.ui.qt import QtCore, QtGui, QtWidgets, Signal
from rigflow.ui.widgets.body_map import BodyMap


class ElidedLabel(QtWidgets.QLabel):
    """Keep full scene names available without widening the panel or column."""

    def __init__(self, heading=False, muted=False):
        super().__init__()
        self.full_text = ""
        self.setProperty("heading", heading)
        self.setProperty("muted", muted)
        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)

    def set_full_text(self, text):
        self.full_text = text
        self.setToolTip(text)
        self._elide()

    def _elide(self):
        self.setText(self.fontMetrics().elidedText(self.full_text, QtCore.Qt.ElideRight, self.contentsRect().width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()


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
        self.selected_role = None
        self._active = False
        self._last_selection = ()
        self._labels = {}
        self.setObjectName("page")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 4, 24, 16)
        layout.setSpacing(10)
        maps_row = QtWidgets.QHBoxLayout()
        maps_row.setSpacing(12)
        self.body_maps, self.panels, self.panel_headers = {}, {}, {}
        self.header_labels, self.count_labels = {}, {}
        self._panel_targets = {}
        for side in ("source", "destination"):
            panel = QtWidgets.QFrame()
            panel.setObjectName("sectionCard")
            panel_layout = QtWidgets.QVBoxLayout(panel)
            panel_layout.setContentsMargins(1, 1, 1, 8)
            panel_layout.setSpacing(4)
            header = QtWidgets.QFrame()
            header.setObjectName("definitionHeader")
            header_layout = QtWidgets.QHBoxLayout(header)
            header_layout.setContentsMargins(10, 10, 10, 10)
            title = ElidedLabel(heading=True)
            count = theme.label("")
            header_layout.addWidget(title, 1)
            header_layout.addWidget(count)
            panel_layout.addWidget(header)
            body = BodyMap(show_labels=False)
            body.setAccessibleName("{} definition map".format(side.title()))
            body.slot_clicked.connect(lambda role, s=side: self.click_slot(role, s))
            body.slot_menu.connect(lambda role, pos, s=side: self.slot_menu(role, pos, s))
            body.background_clicked.connect(lambda s=side: self.activate_panel(s))
            panel_layout.addWidget(body, 1)
            self.body_maps[side], self.panels[side] = body, panel
            self.panel_headers[side], self.header_labels[side], self.count_labels[side] = header, title, count
            for target in (panel, header, title, count):
                target.installEventFilter(self)
                self._panel_targets[target] = side
            panel.setToolTip("Click a slot, then select its joint in Maya. Right-click to clear. Esc cancels.")
        self.centre_column = QtWidgets.QWidget()
        self.centre_column.setFixedWidth(160)
        centre = QtWidgets.QVBoxLayout(self.centre_column)
        centre.setContentsMargins(0, 0, 0, 0)
        centre.setSpacing(8)
        centre.addStretch()
        self.auto_button = theme.button("Auto-match", "Detect joints; keep manual definitions.", self.auto_detect)
        self.unmatch_button = theme.button("Unmatch", "Clear the selected role on both models.", self.unmatch)
        centre.addWidget(self.auto_button)
        centre.addWidget(self.unmatch_button)
        self.map_tabs = QtWidgets.QTabBar()
        self.map_tabs.addTab("Body")
        self.map_tabs.addTab("Hands")
        self.map_tabs.setExpanding(True)
        self.map_tabs.currentChanged.connect(self.set_hands)
        centre.addWidget(self.map_tabs)
        centre.addSpacing(6)
        centre.addWidget(theme.label("Selection", heading=True))
        self.selection_role = ElidedLabel(muted=True)
        self.selection_labels = {side: ElidedLabel(muted=True) for side in self.body_maps}
        centre.addWidget(self.selection_role)
        for label in self.selection_labels.values():
            centre.addWidget(label)
        centre.addSpacing(6)
        self.status_counts = {}
        for state in ("connected", "review", "missing"):
            label = theme.label("", muted=True)
            label.setStyleSheet("font-size: 11px;")
            self.status_counts[state] = label
            centre.addWidget(label)
        centre.addSpacing(8)
        displays = QtWidgets.QHBoxLayout()
        displays.setSpacing(0)
        self.display_buttons = {}
        self.display_group = QtWidgets.QButtonGroup(self)
        self.display = "Both"
        for display in ("Bones", "Mesh", "Both"):
            button = theme.button(display, "Display in the main Maya viewport.", lambda d=display: self.set_display(d))
            button.setStyleSheet("padding: 4px 5px; font-size: 11px; border-radius: 3px;")
            button.setCheckable(True)
            self.display_group.addButton(button)
            self.display_buttons[display] = button
            displays.addWidget(button)
        self.display_buttons["Both"].setChecked(True)
        centre.addLayout(displays)
        self.menu_button = theme.button("…", "Presets and clear model definitions")
        self.menu_button.setFixedWidth(40)
        self.menu_button.setStyleSheet("QPushButton::menu-indicator { image: none; width: 0; }")
        self.preset_menu = QtWidgets.QMenu(self)
        self.preset_menu.addAction("Load preset…", self.load_preset)
        self.preset_menu.addAction("Save preset…", self.save_preset)
        self.clear_actions = {}
        for side in self.body_maps:
            action_class = getattr(QtGui, "QAction", None) or QtWidgets.QAction
            action = action_class("Clear {}".format(controller.definition_label(side)), self.preset_menu)
            action.triggered.connect(lambda checked=False, s=side: self.clear_all(s))
            self.preset_menu.addAction(action)
            self.clear_actions[side] = action
        self.menu_button.setMenu(self.preset_menu)
        centre.addWidget(self.menu_button, 0, QtCore.Qt.AlignHCenter)
        centre.addStretch()
        maps_row.addWidget(self.panels["source"], 1)
        maps_row.addWidget(self.centre_column)
        maps_row.addWidget(self.panels["destination"], 1)
        layout.addLayout(maps_row, 1)
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
                           "QTabBar::tab { background: #3d3d3d; color: #a0a0a0; padding: 6px 8px; }"
                           "QTabBar::tab:selected { color: #23b7db; border-bottom: 2px solid #23b7db; }")

    @property
    def body_map(self):
        """Compatibility for scripts accessing the active definition map."""
        return self.body_maps[self.side]

    def set_hands(self, index):
        for body in self.body_maps.values():
            body.set_hands(index == 1)

    def activate_panel(self, side):
        self.cancel_waiting()
        self.set_side(side)

    def unmatch(self):
        role = self.selected_role
        if role and self.unmatch_button.isEnabled():
            self.cancel_waiting()
            for side in self.body_maps:
                self.controller.set_definition(self.clip_id, role, side, None)

    def _event(self, event, payload):
        if event in (SessionEvent.RIG_CHANGED, SessionEvent.CLIPS_CHANGED):
            self.refresh()
        elif event == SessionEvent.STATUS and self._active:
            self.status_line.setText((payload or {}).get("message", ""))
            self.status_line.setToolTip(self.status_line.text())

    def set_clip(self, clip_id):
        self.clip_id = clip_id
        self.side = "source"
        self.selected_role = None
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
        if watched in self._panel_targets and event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
            self.activate_panel(self._panel_targets[watched])
            return True
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

    def click_slot(self, role, side=None):
        if not self._active or not self._mapping():
            return
        if side is not None:
            self.set_side(side)
        self.selected_role = role
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
        for body in self.body_maps.values():
            body.waiting = None
            body.update()
        self.refresh()

    def clear_slot(self, role, side=None):
        self.cancel_waiting()
        self.controller.set_definition(self.clip_id, role, side or self.side, None)

    def slot_menu(self, role, position, side=None):
        side = side or self.side
        self.set_side(side)
        self.cancel_waiting()
        self.selected_role = role
        self.refresh()
        menu = QtWidgets.QMenu(self)
        joint = joint_for(self._mapping(), role, side)
        menu.addAction("Clear", lambda: self.clear_slot(role, side)).setEnabled(bool(joint))
        menu.addAction("Select in scene", lambda: self.controller.select_definition_joint(joint)).setEnabled(bool(joint))
        menu.exec_(position)

    def clear_all(self, side=None):
        side = side or self.side
        self.cancel_waiting()
        label = self.controller.definition_label(side)
        if QtWidgets.QMessageBox.question(self, "Clear definition?", "Clear all slots on {}?".format(label),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.Yes:
            self.cancel_waiting()
            self.controller.clear_definition(self.clip_id, side)

    def auto_detect(self):
        self.cancel_waiting()
        self.controller.auto_map(self.clip_id)

    def refresh(self):
        mapping = self._mapping()
        counts = {}
        totals = dict(connected=0, review=0, missing=0)
        for side, body in self.body_maps.items():
            skeleton = self.controller.definition_skeleton(self.clip_id, side)
            counts[side] = progress(mapping, side, skeleton)
            character = self.controller.session.source if side == "source" else self.controller.session.destination
            name = character.name if character else (skeleton.name if skeleton else "—")
            label = self.controller.definition_label(side)
            self.header_labels[side].set_full_text("{} · {} · {}".format(label, side, name))
            self.count_labels[side].setText("{}/{}".format(counts[side], len(REQUIRED_ROLES)))
            self.count_labels[side].setStyleSheet("color: {};".format(theme.GREEN if counts[side] == len(REQUIRED_ROLES) else theme.MUTED))
            active = side == self.side
            self.panel_headers[side].setProperty("active", active)
            self.panel_headers[side].setStyleSheet("QFrame#definitionHeader { background: %s; border: 1px solid %s; border-radius: 4px; }" %
                                                 ("#354b52" if active else theme.RAISED, theme.ACCENT if active else theme.BORDER_LIGHT))
            self.clear_actions[side].setText("Clear {}".format(label))
            if self._labels.get(side, (None,))[0] is not skeleton:
                self._labels[side] = (skeleton, label_skeleton(skeleton) if skeleton is not None else None)
            labeling = self._labels.get(side, (None, None))[1]
            present = set(labeling.roles()) if labeling else set()
            if mapping:
                present.update(role for role in mapping.matches if joint_for(mapping, role, side))
            body.set_roles(present)
            roles = body.definition_roles
            body.states = {role: slot_state(mapping, role, side, skeleton or (), labeling) for role in roles}
            body.joints = {role: joint_for(mapping, role, side) for role in roles}
            body.selected_role = self.selected_role
            body.waiting = self.waiting if active else None
            body.update()
            for state in body.states.values():
                if state == "assigned":
                    totals["connected"] += 1
                elif state in ("review", "invalid"):
                    totals["review"] += 1
                elif state == "required":
                    totals["missing"] += 1
            self.selection_labels[side].set_full_text("{}: {}".format(label.replace("Model ", ""), joint_for(mapping, self.selected_role, side) or "—"))
        self.selection_role.set_full_text(display_name(self.selected_role).replace("Fore Arm", "Forearm") if self.selected_role else "—")
        self.unmatch_button.setEnabled(bool(self.selected_role and any(joint_for(mapping, self.selected_role, s) for s in self.body_maps)))
        for state, colour, symbol in (("connected", theme.GREEN, "●"), ("review", theme.YELLOW, "●"), ("missing", theme.RED, "◯")):
            self.status_counts[state].setText('<span style="color:{}">{}</span> {} {}'.format(colour, symbol, totals[state], state.title()))
        self.status_counts["review"].setToolTip("Automatic guesses and invalid definitions across both models.")
        self.status_counts["missing"].setToolTip("Missing required roles across both models; optional slots do not block Transfer.")
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
