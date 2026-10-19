from rigflow.ui.qt import QtWidgets
from rigflow.ui import theme
from rigflow.ui.widgets.section_card import SectionCard


class PlanBanner(SectionCard):
    def __init__(self, parent=None):
        super().__init__("Proposed process", parent=parent)
        self.message_label = theme.label("")
        self.message_label.setWordWrap(True)
        self.issues_label = theme.label("", muted=True)
        self.issues_label.setWordWrap(True)
        self.body.addWidget(self.message_label)
        self.body.addWidget(self.issues_label)
        actions = QtWidgets.QHBoxLayout()
        self.swap_button = theme.button("Swap direction", "Use the other animated model as the source.")
        self.start_button = theme.button("Start", "Start the proposed process for these models.", primary=True)
        actions.addWidget(self.swap_button)
        actions.addStretch()
        actions.addWidget(self.start_button)
        self.body.addLayout(actions)

    def set_plan(self, plan):
        self.title_label.setText(plan.title)
        self.message_label.setText(plan.message)
        self.issues_label.setText("\n".join(plan.issues))
        self.swap_button.setVisible(plan.can_swap)
        self.start_button.setText(plan.action_label or "Nothing to transfer")
        self.start_button.setEnabled(plan.ready)
