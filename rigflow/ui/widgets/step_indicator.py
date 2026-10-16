from rigflow.ui.qt import QtWidgets, Signal
from rigflow.ui import theme


class StepIndicator(QtWidgets.QWidget):
    step_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_step = 1
        self.buttons = []
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for step, name in enumerate(("Setup", "Match", "Transfer"), 1):
            if step > 1:
                layout.addWidget(theme.label("·", muted=True))
            button = theme.button(name, "Open step {}: {} when available.".format(step, name))
            button.clicked.connect(lambda checked=False, value=step: self.step_requested.emit(value))
            layout.addWidget(button)
            self.buttons.append(button)
        self.set_state(1)

    def set_state(self, current, allowed=(1,), completed=()):
        self.current_step = current
        for step, button in enumerate(self.buttons, 1):
            button.setText("{} {}".format("✓" if step in completed else step, ("Setup", "Match", "Transfer")[step - 1]))
            button.setEnabled(step in allowed)
            color = theme.ACCENT if step == current else (theme.TEXT if step in completed else theme.MUTED)
            button.setStyleSheet("QPushButton { background: transparent; border: none; color: %s; padding: 8px; } QPushButton:hover { background: %s; }" % (color, theme.RAISED))
