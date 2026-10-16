"""Maya shelf entry point and standalone single-window launcher."""
from __future__ import annotations

import importlib
import sys
from rigflow.core import config
from rigflow.ui.qt import QtCore, QtWidgets, maya_main_window

_window = None
_application = None


def show(dev_reload=False):
    """Raise the singleton, replacing stale/development instances when necessary.

    The application reference is retained for standalone mayapy use. This
    function does not start a nested event loop in Maya or an existing host.
    """
    global _window, _application
    app = QtWidgets.QApplication.instance()
    if app is None:
        _application = QtWidgets.QApplication(sys.argv[:1])
        app = _application
    from rigflow.ui.main_window import MainWindow
    candidates = [w for w in app.allWidgets() if w.objectName() == config.WINDOW_OBJECT_NAME]
    for old in candidates:
        if not dev_reload and isinstance(old, MainWindow) and not old._disposed:
            _window = old
            old.show()
            old.raise_()
            old.activateWindow()
            return old
        old.close()
        old.deleteLater()
    if candidates:
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    if dev_reload:
        # Only the UI is ours to reload; core/service state may be in use elsewhere.
        names = sorted((name for name in sys.modules if name.startswith("rigflow.ui.") and
                        name not in ("rigflow.ui.launcher", "rigflow.ui.qt")),
                       key=lambda name: (name.count("."), name), reverse=True)
        # Dependency-first order prevents views retaining old widget classes.
        for prefix in ("rigflow.ui.theme", "rigflow.ui.controller", "rigflow.ui.widgets.",
                       "rigflow.ui.help_menu", "rigflow.ui.matching_view", "rigflow.ui.review_view",
                       "rigflow.ui.fake_controller", "rigflow.ui.main_window"):
            for name in names:
                if name == prefix or (prefix.endswith(".") and name.startswith(prefix)):
                    importlib.reload(sys.modules[name])
        MainWindow = importlib.import_module("rigflow.ui.main_window").MainWindow
    from rigflow.ui.controller import Controller
    _window = MainWindow(Controller(), parent=maya_main_window())
    if maya_main_window() is not None:
        _window.show(dockable=True)
    else:
        _window.show()
    _window.raise_()
    _window.activateWindow()
    return _window
