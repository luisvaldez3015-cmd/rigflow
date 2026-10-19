"""Setup adds whole models and renders the process proposed by Session."""
from rigflow.core.character import model_label
from rigflow.ui.qt import QtCore, QtWidgets
from rigflow.ui import theme
from rigflow.ui.widgets.add_tile import AddTile
from rigflow.ui.widgets.drop_area import DropArea
from rigflow.ui.widgets.model_card import ModelCard
from rigflow.ui.widgets.plan_banner import PlanBanner


class ModelDropArea(QtWidgets.QFrame):
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.callback = callback
        self.setAcceptDrops(True)
        self.setToolTip("Drop one .ma, .mb, .fbx or .obj model here.")

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and DropArea.accepts(urls[0].toLocalFile()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and DropArea.accepts(urls[0].toLocalFile()):
            self.callback(urls[0].toLocalFile())
            event.acceptProposedAction()


class SetupView(QtWidgets.QWidget):
    def __init__(self, window):
        super().__init__()
        self.setObjectName("page")
        self.window, self.session = window, window.session
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 16)
        layout.setSpacing(16)
        self.empty_area = ModelDropArea(window.add_path)
        empty = QtWidgets.QVBoxLayout(self.empty_area)
        empty.setSpacing(12)
        empty.addStretch()
        self.add_tile = AddTile()
        self.add_tile.clicked.connect(window.show_add_menu)
        empty.addWidget(self.add_tile, 0, QtCore.Qt.AlignHCenter)
        title = theme.label("Add a model", heading=True)
        title.setAlignment(QtCore.Qt.AlignCenter)
        empty.addWidget(title)
        self.caption = theme.label("", muted=True)
        self.caption.setWordWrap(True)
        self.caption.setAlignment(QtCore.Qt.AlignCenter)
        self.caption.setFixedWidth(540)
        self.caption.setMinimumHeight(48)
        empty.addWidget(self.caption, 0, QtCore.Qt.AlignHCenter)
        empty.addStretch()
        layout.addWidget(self.empty_area, 1)
        self.populated_area = QtWidgets.QWidget()
        populated = QtWidgets.QVBoxLayout(self.populated_area)
        populated.setContentsMargins(0, 0, 0, 0)
        populated.setSpacing(16)
        populated.addWidget(theme.label("Your models", heading=True))
        self.models_row = QtWidgets.QHBoxLayout()
        self.models_row.setSpacing(16)
        self.model_cards = []
        populated.addLayout(self.models_row)
        self.second_area = ModelDropArea(window.add_path)
        second = QtWidgets.QVBoxLayout(self.second_area)
        second.setSpacing(8)
        self.small_add_tile = AddTile(40)
        self.small_add_tile.clicked.connect(window.show_add_menu)
        second.addWidget(self.small_add_tile, 0, QtCore.Qt.AlignHCenter)
        self.second_label = theme.label("Add the second model", heading=True)
        second.addWidget(self.second_label, 0, QtCore.Qt.AlignHCenter)
        self.second_caption = theme.label("", muted=True)
        self.second_caption.setWordWrap(True)
        self.second_caption.setAlignment(QtCore.Qt.AlignCenter)
        second.addWidget(self.second_caption)
        populated.addWidget(self.second_area)
        self.plan_banner = PlanBanner()
        self.plan_banner.swap_button.clicked.connect(window.controller.swap_direction)
        self.plan_banner.start_button.clicked.connect(window.start_plan)
        populated.addWidget(self.plan_banner)
        populated.addStretch(1)
        layout.addWidget(self.populated_area, 1)
        self.validation_label = self.plan_banner.issues_label

    def refresh(self):
        characters, plan = self.session.characters, self.session.plan
        self.empty_area.setVisible(not characters)
        self.populated_area.setVisible(bool(characters))
        self.caption.setText(plan.message)
        self.second_caption.setText(plan.message)
        self.second_area.setVisible(len(characters) == 1)
        self.plan_banner.setVisible(len(characters) >= 2)
        self.plan_banner.set_plan(plan)
        ids = [c.character_id for c in characters]
        if [c.character_id for c in self.model_cards] != ids:
            for card in self.model_cards:
                self.models_row.removeWidget(card)
                card.hide()
                card.deleteLater()
            self.model_cards = []
            for index, character in enumerate(characters):
                card = ModelCard(character, model_label(index))
                card.replace_requested.connect(self.window.replace_model)
                card.remove_requested.connect(self.window.controller.remove_model)
                card.file_dropped.connect(self.window.controller.replace_model_from_file)
                self.models_row.addWidget(card, 1)
                self.model_cards.append(card)
        for index, (card, character) in enumerate(zip(self.model_cards, characters)):
            card.set_character(character, model_label(index))
