"""RigFlow brand assets drawn with Qt.

The logo is the word *RigFlow* with the "i" replaced by a stylised Maya joint
(a sphere, a bone tapering down, a small sphere at the tip) in brand cyan.
Inside Maya only the joint glyph is used (shelf and window icons); the UI
header redraws the full wordmark as vectors so it stays crisp on any DPI and
adapts to the dark theme.

Geometry below was measured on the official 1024 px logo (``assets/logo.png``)
and is expressed relative to the glyph height ``h``.
"""

from __future__ import annotations

from rigflow.ui.qt import QtCore, QtGui

#: Brand colours sampled from the official logo.
CYAN = "#23b7db"
NAVY = "#10203f"
#: Glyph width as a fraction of its height.
GLYPH_ASPECT = 0.25


def paint_joint_glyph(painter: QtGui.QPainter, rect: QtCore.QRectF, color=CYAN) -> None:
    """Draw the joint glyph centred inside ``rect`` (keeps its aspect ratio)."""
    h = min(rect.height(), rect.width() / GLYPH_ASPECT)
    w = h * GLYPH_ASPECT
    x0 = rect.center().x()
    y0 = rect.center().y() - h / 2.0

    painter.save()
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(color))

    # Head sphere
    head_r = 0.09 * h
    painter.drawEllipse(QtCore.QPointF(x0, y0 + 0.09 * h), head_r, head_r)

    # Bone: narrow neck under the head, widest shoulders, tapering to the tip
    bone = QtGui.QPainterPath()
    bone.moveTo(x0, y0 + 0.215 * h)
    bone.lineTo(x0 + 0.5 * w, y0 + 0.30 * h)
    bone.lineTo(x0 + 0.06 * w, y0 + 0.86 * h)
    bone.lineTo(x0 - 0.06 * w, y0 + 0.86 * h)
    bone.lineTo(x0 - 0.5 * w, y0 + 0.30 * h)
    bone.closeSubpath()
    painter.drawPath(bone)

    # Tip sphere
    tip_r = 0.065 * h
    painter.drawEllipse(QtCore.QPointF(x0, y0 + 0.935 * h), tip_r, tip_r)
    painter.restore()


def glyph_pixmap(size: int, color=CYAN, margin: float = 0.06) -> QtGui.QPixmap:
    """Transparent square pixmap with the glyph (used for icons)."""
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    inset = size * margin
    paint_joint_glyph(painter, QtCore.QRectF(inset, inset, size - 2 * inset, size - 2 * inset), color)
    painter.end()
    return pixmap


def glyph_icon(size: int = 64, color=CYAN) -> QtGui.QIcon:
    return QtGui.QIcon(glyph_pixmap(size, color))


def paint_wordmark(painter: QtGui.QPainter, rect: QtCore.QRectF, text_color, accent=CYAN,
                   font: QtGui.QFont = None) -> float:
    """Draw ``R`` + joint glyph + ``gFlow`` left-aligned in ``rect``.

    Returns the width actually used, so callers can size the widget. The glyph
    stands where the dot and stem of the "i" would be and is slightly taller
    than the x-height, like in the logo.
    """
    painter.save()
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
    if font is None:
        font = QtGui.QFont("Segoe UI", int(rect.height() * 0.55))
        font.setWeight(QtGui.QFont.Bold)
    painter.setFont(font)
    metrics = QtGui.QFontMetricsF(font)
    baseline = rect.top() + (rect.height() + metrics.capHeight()) / 2.0
    x = rect.left()
    painter.setPen(QtGui.QColor(text_color))
    painter.drawText(QtCore.QPointF(x, baseline), "R")
    x += metrics.horizontalAdvance("R") + metrics.horizontalAdvance(" ") * 0.15
    glyph_h = metrics.capHeight() * 1.25
    glyph_rect = QtCore.QRectF(x, baseline - metrics.capHeight() * 1.05, glyph_h * GLYPH_ASPECT, glyph_h)
    paint_joint_glyph(painter, glyph_rect, accent)
    x += glyph_rect.width() + metrics.horizontalAdvance(" ") * 0.35
    painter.drawText(QtCore.QPointF(x, baseline), "gFlow")
    x += metrics.horizontalAdvance("gFlow")
    painter.restore()
    return x - rect.left()
