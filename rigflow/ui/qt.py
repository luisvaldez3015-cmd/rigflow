"""The only Qt binding imports used by the interface."""
from __future__ import annotations

import os

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
    QT_BINDING = "PySide6"
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance
    QT_BINDING = "PySide2"

Signal = QtCore.Signal
Slot = QtCore.Slot
Property = QtCore.Property


def ensure_application_fonts():
    """Supply Windows fonts when Maya's offscreen plugin has an empty database.

    A live Maya uses its existing font database unchanged. No bundled fonts or
    system settings are needed; the offscreen platform does not discover them.
    """
    families = QtGui.QFontDatabase.families() if QT_BINDING == "PySide6" else QtGui.QFontDatabase().families()
    if families:
        return
    font_dir = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")
    for name in ("segoeui.ttf", "seguisb.ttf", "seguisym.ttf"):
        path = os.path.join(font_dir, name)
        if os.path.isfile(path):
            QtGui.QFontDatabase.addApplicationFont(path)
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.setFont(QtGui.QFont("Segoe UI", 9))


def maya_main_window():
    """Return Maya's main QWidget, or None in mayapy / standalone Qt."""
    try:
        from rigflow.core import compat
        # MQtUtil.mainWindow can access-violate in an uninitialized mayapy.
        # Check the host before crossing that C++ boundary, even if Qt imports.
        if QtWidgets.QApplication.instance() is None or not compat.in_maya() or compat.is_batch():
            return None
        from maya import OpenMayaUI as omui
        pointer = omui.MQtUtil.mainWindow()
        return wrapInstance(int(pointer), QtWidgets.QWidget) if pointer else None
    except Exception:
        return None
