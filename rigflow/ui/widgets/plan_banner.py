"""Setup process cards render pure options supplied by Session."""
from rigflow.ui.qt import QtWidgets, Signal
from rigflow.ui import theme
from rigflow.ui.widgets.section_card import SectionCard
from rigflow.ui.widgets.status_badge import StatusBadge


class ProcessCard(SectionCard):
    start_requested = Signal(object)

    def __init__(self, title, parent=None):
        super().__init__(title, parent=parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        row = QtWidgets.QHBoxLayout()
        self.similarity_label = theme.label("")
        self.verdict = StatusBadge("", theme.GRAY)
        row.addWidget(self.similarity_label)
        row.addStretch()
        row.addWidget(self.verdict)
        self.body.addLayout(row)
        self.similarity_bar = QtWidgets.QProgressBar()
        self.similarity_bar.setRange(0, 100)
        self.similarity_bar.setTextVisible(False)
        self.similarity_bar.setFixedHeight(5)
        self.body.addWidget(self.similarity_bar)
        self.differing_label = theme.label("", muted=True)
        self.differing_label.setWordWrap(True)
        self.body.addWidget(self.differing_label)
        self.reason_label = theme.label("", muted=True)
        self.reason_label.setWordWrap(True)
        self.body.addWidget(self.reason_label)
        actions = QtWidgets.QHBoxLayout()
        self.swap_button = theme.button("Swap direction", "Use the other animated model as the source.")
        self.start_button = theme.button("Start", "Start this process.", primary=True)
        self.start_button.clicked.connect(lambda: self.start_requested.emit(self.option.kind))
        actions.addWidget(self.swap_button)
        actions.addStretch()
        actions.addWidget(self.start_button)
        self.body.addLayout(actions)

    def set_option(self, option):
        self.option = option
        self.title_label.setText(option.title)
        self.title_label.setStyleSheet("color: %s;" % (theme.TEXT if option.available else theme.GRAY))
        self.start_button.setText(option.action_label)
        self.start_button.setEnabled(option.available)
        self.reason_label.setText("⚠ " + option.reason if option.reason else "")
        self.reason_label.setVisible(bool(option.reason))
        self.swap_button.setVisible(option.can_swap)
        similarity = option.similarity
        is_rig = option.action_label == "Start Rig"
        self.similarity_label.setVisible(is_rig)
        self.verdict.setVisible(is_rig and similarity is not None)
        self.similarity_bar.setVisible(is_rig and similarity is not None)
        self.differing_label.setVisible(is_rig and bool(similarity and similarity.differing))
        if is_rig:
            self.similarity_label.setText("Mesh similarity {:.0f}%".format(similarity.score) if similarity else "Mesh similarity unavailable")
        if similarity:
            color = theme.GREEN if similarity.matches else theme.RED
            self.verdict.set_status("Meshes match" if similarity.matches else "Meshes don't match", color)
            self.similarity_bar.setValue(round(similarity.score))
            self.similarity_bar.setStyleSheet("QProgressBar { border: none; background: #414141; } QProgressBar::chunk { background: %s; }" % color)
            self.differing_label.setText("Differs around: " + ", ".join(similarity.differing))


class PlanBanner(QtWidgets.QWidget):
    """Compatibility container for the two vertically stacked process cards."""
    start_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.rig_card = ProcessCard("Transfer rig")
        self.animation_card = ProcessCard("Transfer animation")
        self.cards = [self.rig_card, self.animation_card]
        for card in self.cards:
            layout.addWidget(card)
            card.start_requested.connect(self.start_requested.emit)
        self.issues_label = theme.label("", muted=True)
        self.issues_label.setWordWrap(True)
        layout.addWidget(self.issues_label)
        self.swap_button = self.animation_card.swap_button
        self.start_button = self.animation_card.start_button

    def set_plan(self, plan):
        for card, option in zip(self.cards, plan.options):
            card.set_option(option)
        self.start_button = self.rig_card.start_button if plan.first_step == "rig" else self.animation_card.start_button
        self.issues_label.setText("\n".join(plan.issues))
        self.issues_label.setVisible(bool(plan.issues))
