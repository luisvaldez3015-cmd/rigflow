from __future__ import annotations

from rigflow.core import config
from rigflow.ui.qt import QtWidgets


def add_help_menu(window, controller):
    """Build documentation entries from central config, plus support and About."""
    menu = window.menuBar().addMenu("Help")
    for title, path in config.DOCS.items():
        action = menu.addAction(title)
        action.triggered.connect(lambda checked=False, p=path: controller.open_url(config.REPO_URL + "/blob/main/" + p))
    menu.addSeparator()
    demo = menu.addAction("Create demo scene")
    demo.setToolTip("Build two sample characters (Mixamo-style source with a jump, short destination "
                    "with a skinned proxy mesh and a facial control) to try the whole workflow.")
    demo.triggered.connect(lambda: controller.create_demo_scene())
    menu.addSeparator()
    repo = menu.addAction("GitHub Repository")
    repo.triggered.connect(lambda: controller.open_url(config.REPO_URL))
    issue = menu.addAction("Report an Issue")
    issue.triggered.connect(lambda: controller.open_url(config.ISSUES_URL))
    menu.addSeparator()

    def about():
        environment = controller.environment()
        details = "\n".join("{}: {}".format(k.replace("_", " ").title(), v) for k, v in environment.items())
        QtWidgets.QMessageBox.about(window, "About RigFlow", "RigFlow — Animation Transfer for Maya\nOpen-source animation tools\n\n" + details)

    menu.addAction("About RigFlow").triggered.connect(about)
    return menu
