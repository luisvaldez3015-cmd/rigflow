"""Render RigFlow's icons from the brand glyph.

    mayapy scripts/make_icons.py

Writes transparent PNGs into ``assets/icons`` (shelf 32/64 px, window 128 px,
brand 512 px) and a wordmark preview, all drawn by ``rigflow.ui.brand`` so the
Maya icons, the UI header and ``assets/icon.svg`` share one geometry.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rigflow.ui import brand  # noqa: E402
from rigflow.ui.qt import QtCore, QtGui, QtWidgets, ensure_application_fonts  # noqa: E402

OUT_DIR = os.path.join(ROOT, "assets", "icons")


def wordmark_preview(width: int = 640, height: int = 160, background="#373737") -> QtGui.QImage:
    image = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)
    image.fill(QtGui.QColor(background))
    painter = QtGui.QPainter(image)
    brand.paint_wordmark(painter, QtCore.QRectF(24, 24, width - 48, height - 48), "#e6e6e6")
    painter.end()
    return image


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)  # noqa: F841
    ensure_application_fonts()
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    outputs = {
        "rigflow_shelf.png": 32,
        "rigflow_shelf_64.png": 64,
        "rigflow_window.png": 128,
        "rigflow_glyph_512.png": 512,
    }
    for name, size in outputs.items():
        path = os.path.join(OUT_DIR, name)
        if not brand.glyph_pixmap(size).save(path, "PNG"):
            print("Failed to write", path)
            return 1
        print("Wrote", path)
    preview = os.path.join(OUT_DIR, "rigflow_wordmark_dark.png")
    wordmark_preview().save(preview, "PNG")
    print("Wrote", preview)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.exit(main())
