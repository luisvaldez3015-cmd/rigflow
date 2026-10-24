"""Silhouette comparison sheet (references next to the RigFlow art) + debug overlays.

mayapy -I compare.py <asset dir> <out png> [<overlay dir>]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402
from PySide2 import QtCore, QtGui, QtSvg, QtWidgets  # noqa: E402

ASSETS, OUT = sys.argv[1], sys.argv[2]
OVL = sys.argv[3] if len(sys.argv) > 3 else None
REF = os.environ.get("RIGFLOW_ART_REFERENCES", "")
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def path_of(pts):
    path = QtGui.QPainterPath()
    path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(*p) for p in geom.sample_catmull(pts, steps=24)]))
    path.closeSubpath()
    return path


BODY = path_of(geom.body_outline())
LHAND = path_of(geom.hand_outline_left())

PH = 600                       # panel height in px
GAP = 24


def panel_ref(name):
    return QtGui.QImage(os.path.join(REF, name))


def panel_sil(path, crop):
    x0, y0, w, h = crop
    s = PH / float(h)
    img = QtGui.QImage(int(w * s), PH, QtGui.QImage.Format_ARGB32_Premultiplied)
    img.fill(QtGui.QColor("white"))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.scale(s, s)
    p.translate(-x0, -y0)
    p.fillPath(path, QtGui.QColor("black"))
    p.end()
    return img


def panel_svg(svg, crop):
    x0, y0, w, h = crop
    s = PH / float(h)
    img = QtGui.QImage(int(w * s), PH, QtGui.QImage.Format_ARGB32_Premultiplied)
    img.fill(QtGui.QColor("#2f2f2f"))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    QtSvg.QSvgRenderer(os.path.join(ASSETS, svg)).render(p, QtCore.QRectF(-x0 * s, -y0 * s, 1000 * s, 640 * s))
    p.end()
    return img


BODY_CROP = (300, 0, 400, 640)
HAND_CROP = (500, 0, 500, 640)
rows = [
    [("Reference (body)", panel_ref("body_reference.png")),
     ("RigFlow body.svg, silhouette", panel_sil(BODY, BODY_CROP)),
     ("RigFlow body.svg, as drawn", panel_svg("body.svg", BODY_CROP))],
    [("Reference (hand)", panel_ref("hand_reference.png")),
     ("RigFlow hands.svg (left hand), silhouette", panel_sil(LHAND, HAND_CROP)),
     ("RigFlow hands.svg (left hand), as drawn", panel_svg("hands.svg", HAND_CROP))],
]
# Reference photos are optional local inputs, not shipped repository assets.
rows = [[(title, im) for title, im in row if not im.isNull()] for row in rows]
W = max(sum(im.width() for _, im in r) + GAP * (len(r) + 1) for r in rows)
TITLE = 28
Hh = len(rows) * (PH + TITLE) + GAP * (len(rows) + 1)
sheet = QtGui.QImage(W, Hh, QtGui.QImage.Format_ARGB32_Premultiplied)
sheet.fill(QtGui.QColor("#e9e9e9"))
p = QtGui.QPainter(sheet)
p.setRenderHint(QtGui.QPainter.Antialiasing)
f = QtGui.QFont("Segoe UI")
f.setPixelSize(15)
p.setFont(f)
y = GAP
for r in rows:
    x = GAP
    for title, im in r:
        p.setPen(QtGui.QColor("#333333"))
        p.drawText(QtCore.QRectF(x, y, im.width(), TITLE - 6), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, title)
        p.drawImage(x, y + TITLE, im)
        p.setPen(QtGui.QPen(QtGui.QColor("#bbbbbb"), 1))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRect(x, y + TITLE, im.width(), im.height())
        x += im.width() + GAP
    y += PH + TITLE + GAP
p.end()
sheet.save(OUT)

if OVL:
    # Debug only: the reference drawn into the design-unit mapping, my contour on top.
    for name, ref, mapper, path, crop, joints in (
            ("body", "body_reference.png", (geom.BOX, geom.BOY, geom.BK), BODY, BODY_CROP, geom.BODY_JOINTS),
            ("hand", "hand_reference.png", (geom.HOX, geom.HOY, geom.HK), LHAND, HAND_CROP, geom.HAND_JOINTS)):
        x0, y0, w, h = crop
        s = 1000.0 / h
        img = QtGui.QImage(int(w * s), int(h * s), QtGui.QImage.Format_ARGB32_Premultiplied)
        img.fill(QtGui.QColor("white"))
        p = QtGui.QPainter(img)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.scale(s, s)
        p.translate(-x0, -y0)
        ox, oy, k = mapper
        p.setOpacity(0.35)
        p.drawImage(QtCore.QRectF(ox, oy, 400 * k, 600 * k), panel_ref(ref))
        p.setOpacity(1.0)
        p.setPen(QtGui.QPen(QtGui.QColor("#d0302a"), 1.0 / s * 1.5))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawPath(path)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(35, 140, 219, 200))
        for jx, jy in joints.values():
            p.drawEllipse(QtCore.QPointF(jx, jy), 3, 3)
        p.end()
        img.save(os.path.join(OVL, "ovl_%s.png" % name))
