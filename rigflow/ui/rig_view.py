from rigflow.ui.qt import QtWidgets, Signal
from rigflow.ui import theme
from rigflow.ui.widgets.viewport_panel import ViewportPanel


class RigView(QtWidgets.QWidget):
    back_requested = Signal()
    bound = Signal(dict)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("page")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 16)
        layout.setSpacing(12)
        self.title = theme.label("Fit the rig", heading=True)
        layout.addWidget(self.title)
        self.viewport = ViewportPanel("Destination · fitted skeleton", controller, "destination")
        layout.addWidget(self.viewport, 1)
        self.info_label = theme.label("", muted=True)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        actions = QtWidgets.QHBoxLayout()
        self.back_button = theme.button("‹ Back", "Remove the fitted skeleton and return to Setup.", self.back)
        self.refit_button = theme.button("Refit", "Remove the current fit and fit a fresh skeleton to the mesh.", self.refit)
        self.bind_button = theme.button("Bind skin ›", "Bind the fitted skeleton to the destination mesh and continue.", self.bind, True)
        actions.addWidget(self.back_button)
        actions.addStretch()
        actions.addWidget(self.refit_button)
        actions.addWidget(self.bind_button)
        layout.addLayout(actions)

    def set_fit(self, fit):
        destination = self.controller.session.destination
        label = self.controller.session.label_for(destination.character_id) if destination else "Destination"
        self.title.setText("Fit the rig · {} · {}".format(label, destination.name if destination else ""))
        text = "Scale {:.3g} · {} joints. Move joints in Maya if needed, then Bind.".format(fit.scale, len(fit.joints)) if fit else "No fitted rig. Return to Setup to start again."
        if fit and fit.warnings:
            text += "\n" + "\n".join(fit.warnings)
        self.info_label.setText(text)
        self.bind_button.setEnabled(fit is not None)
        self.viewport.configure(self.controller.rig_viewport_nodes(), label + " · fitted skeleton")

    def activate(self):
        self.set_fit(self.controller.rig_fit())

    def deactivate(self):
        self.viewport.release()

    def dispose(self):
        self.deactivate()

    def refit(self):
        self.deactivate()
        self.set_fit(self.controller.refit_rig())

    def back(self):
        self.deactivate()
        if self.controller.cancel_rig_fit():
            self.back_requested.emit()

    def bind(self):
        self.deactivate()
        result = self.controller.bind_rig()
        if result:
            self.bound.emit(result)
        else:
            self.set_fit(self.controller.rig_fit())
