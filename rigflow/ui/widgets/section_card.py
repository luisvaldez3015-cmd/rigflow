from __future__ import annotations

from rigflow.ui.qt import QtWidgets
from rigflow.ui import theme


class SectionCard(QtWidgets.QFrame):
    """Rounded section with a stable title, optional subtitle and header actions."""

    def __init__(self, title, subtitle="", parent=None):
        super().__init__(parent)
        self.setObjectName("sectionCard")
        self.title = title
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)
        self.header = QtWidgets.QHBoxLayout()
        self.title_label = theme.label(title, heading=True)
        self.header.addWidget(self.title_label)
        self.header.addStretch()
        layout.addLayout(self.header)
        if subtitle:
            layout.addWidget(theme.label(subtitle, muted=True))
        self.body = QtWidgets.QVBoxLayout()
        self.body.setSpacing(8)
        layout.addLayout(self.body)

    def add_action(self, widget):
        self.header.addWidget(widget)
