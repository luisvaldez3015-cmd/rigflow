"""Render RigFlow's icons (shelf button, window icon) with Qt.

    mayapy scripts/make_icons.py

Writes PNGs into ``assets/icons``. The design mirrors ``assets/icon.svg``:
a joint chain flowing from left to right, drawn in the accent blue on a
dark rounded tile so it reads at 32 px on a Maya shelf.
"""

from __future__ import annotations

import os
import sys

try:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
except ImportError:  # pragma: no cover - Maya 2023/2024
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "icons")

TILE_TOP = "#33404f"
TILE_BOTTOM = "#1f2831"
ACCENT = "#5b9bd5"
ACCENT_LIGHT = "#9ccbf0"
JOINT_FILL = "#e8eef4"


def paint_icon(size: int) -> QtGui.QImage:
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    s = size / 64.0  # design space is 64 x 64

    # Tile
    gradient = QtGui.QLinearGradient(0, 0, 0, size)
    gradient.setColorAt(0.0, QtGui.QColor(TILE_TOP))
    gradient.setColorAt(1.0, QtGui.QColor(TILE_BOTTOM))
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QBrush(gradient))
    painter.drawRoundedRect(QtCore.QRectF(0, 0, size, size), 14 * s, 14 * s)

    # Flow curve: from the lower-left joint up through the middle to the upper-right joint
    path = QtGui.QPainterPath()
    path.moveTo(14 * s, 46 * s)
    path.cubicTo(22 * s, 18 * s, 40 * s, 52 * s, 50 * s, 18 * s)
    pen = QtGui.QPen(QtGui.QColor(ACCENT), 5 * s, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.drawPath(path)

    # Arrow head at the end of the curve
    head = QtGui.QPolygonF([
        QtCore.QPointF(50 * s, 12 * s),
        QtCore.QPointF(56 * s, 22 * s),
        QtCore.QPointF(44 * s, 22 * s),
    ])
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(ACCENT_LIGHT))
    painter.drawPolygon(head)

    # Joints
    for center, radius in ((QtCore.QPointF(14 * s, 46 * s), 6 * s), (QtCore.QPointF(31 * s, 36 * s), 4.5 * s)):
        painter.setBrush(QtGui.QColor(JOINT_FILL))
        painter.setPen(QtGui.QPen(QtGui.QColor(TILE_BOTTOM), 1.5 * s))
        painter.drawEllipse(center, radius, radius)

    painter.end()
    return image


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)  # noqa: F841
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    outputs = {
        "rigflow_shelf.png": 32,
        "rigflow_shelf_64.png": 64,
        "rigflow_window.png": 128,
    }
    for name, size in outputs.items():
        path = os.path.join(OUT_DIR, name)
        if not paint_icon(size).save(path, "PNG"):
            print("Failed to write", path)
            return 1
        print("Wrote", path)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.exit(main())
