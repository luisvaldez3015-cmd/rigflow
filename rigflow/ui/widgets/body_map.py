"""HumanIK-style definition map rendered from the checked-in art layout.

The SVGs contain only the mannequin silhouettes. Coordinates, bones, labels,
colours and state sizes live in ``assets/definition/layout.json`` so the art
can be regenerated without a second coordinate table in Python.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from rigflow.skeleton.roles import REQUIRED_ROLES, display_name
from rigflow.ui.qt import QtCore, QtGui, QtWidgets, Signal, QtSvg


_DEFINITION_DIR = Path(__file__).resolve().parents[3] / "assets" / "definition"


def _load_layout():
    with open(_DEFINITION_DIR / "layout.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


_LAYOUT = _load_layout()


def _positions(view):
    return {role: (item["x"], item["y"]) for role, item in _LAYOUT[view]["joints"].items()}


# Public compatibility aliases; the coordinates themselves remain in layout.json.
BODY_SLOTS = _positions("body")


def hand_slots():
    return _positions("hands")


def _qcolor(value, alpha=1.0):
    colour = QtGui.QColor(value)
    colour.setAlphaF(alpha)
    return colour


def _font(style, size, weight=QtGui.QFont.Normal, spacing=0.0):
    font = QtGui.QFont(style.get("family", "Segoe UI"))
    font.setPixelSize(int(round(size)))
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, spacing)
    return font


class BodyMap(QtWidgets.QWidget):
    """Clickable body/hand slots with the same geometry used for painting."""

    slot_clicked = Signal(str)
    slot_menu = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hands = False
        self.states, self.joints = {}, {}
        self.waiting = None
        self.hovered = None
        self.setMouseTracking(True)
        self.setMinimumSize(500, 250)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setAccessibleName("Character definition body map")
        self._renderers = {}
        for view in ("body", "hands"):
            svg_path = _DEFINITION_DIR / _LAYOUT[view]["svg"]
            self._renderers[view] = QtSvg.QSvgRenderer(str(svg_path), self)

    @property
    def slots(self):
        return hand_slots() if self.hands else BODY_SLOTS

    def set_hands(self, enabled):
        enabled = bool(enabled)
        if self.hands != enabled:
            self.hands = enabled
            self.hovered = None
            self.update()

    def _view_name(self):
        return "hands" if self.hands else "body"

    def _transform(self):
        width, height = _LAYOUT["viewBox"][2], _LAYOUT["viewBox"][3]
        scale = min(self.width() / float(width), self.height() / float(height))
        return scale, (self.width() - width * scale) / 2.0, (self.height() - height * scale) / 2.0

    def _screen_point(self, role):
        scale, ox, oy = self._transform()
        item = _LAYOUT[self._view_name()]["joints"][role]
        return QtCore.QPointF(ox + item["x"] * scale, oy + item["y"] * scale)

    def _radius(self, role, scale=None):
        view = self._view_name()
        scale = self._transform()[0] if scale is None else scale
        item = _LAYOUT[view]["joints"][role]
        minima = _LAYOUT["style"]["jointMinRadiusPx"][view]
        return max(float(minima["required" if item.get("required") else "optional"]), item["r"] * scale)

    def slot_position(self, role):
        point = self._screen_point(role)
        return QtCore.QPoint(round(point.x()), round(point.y()))

    def role_at(self, position):
        point = QtCore.QPointF(position)
        scale = self._transform()[0]
        for role in self.slots:
            centre = self._screen_point(role)
            hit = max(self._radius(role, scale) + 4.0, 10.0)
            if (centre.x() - point.x()) ** 2 + (centre.y() - point.y()) ** 2 <= hit * hit:
                return role
        return None

    def mousePressEvent(self, event):
        role = self.role_at(event.pos())
        if role:
            if event.button() == QtCore.Qt.RightButton:
                self.slot_menu.emit(role, event.globalPos())
            elif event.button() == QtCore.Qt.LeftButton:
                self.slot_clicked.emit(role)
        event.accept()

    def mouseMoveEvent(self, event):
        role = self.role_at(event.pos())
        if role != self.hovered:
            self.hovered = role
            self.setCursor(QtCore.Qt.PointingHandCursor if role else QtCore.Qt.ArrowCursor)
            if role:
                required = _LAYOUT[self._view_name()]["joints"][role].get("required", False)
                status = "Required" if required or role in REQUIRED_ROLES else "Optional"
                self.setToolTip("{} · {}\n{}".format(
                    display_name(role), status,
                    self.joints.get(role) or "Click, then select a joint in Maya"))
            else:
                self.setToolTip("")
            self.update()
        event.accept()

    def leaveEvent(self, event):
        self.hovered = None
        self.update()
        super().leaveEvent(event)

    @staticmethod
    def _bone_polys(parent, child, parent_radius, child_radius):
        dx, dy = child.x() - parent.x(), child.y() - parent.y()
        distance = math.hypot(dx, dy)
        if distance < 1e-6:
            return None
        ux, uy = dx / distance, dy / distance
        nx, ny = -uy, ux
        a = min(parent_radius * 1.25, distance * 0.3)
        half_width = parent_radius * 0.62
        w1 = QtCore.QPointF(parent.x() + ux * a + nx * half_width,
                            parent.y() + uy * a + ny * half_width)
        w2 = QtCore.QPointF(parent.x() + ux * a - nx * half_width,
                            parent.y() + uy * a - ny * half_width)
        tip = QtCore.QPointF(child.x() - ux * (child_radius + 1.5),
                             child.y() - uy * (child_radius + 1.5))
        light_first = nx * -0.6 + ny * -0.8 > 0
        first, second = [parent, w1, tip], [parent, tip, w2]
        facets = (first, second) if light_first else (second, first)
        return facets, [parent, w1, tip, w2]

    @staticmethod
    def _polygon(points):
        return QtGui.QPolygonF(points)

    def _state(self, role):
        view = _LAYOUT[self._view_name()]
        if role == self.waiting:
            return "waiting"
        return self.states.get(role, "required" if view["joints"][role].get("required") else "empty")

    def _bone_kind(self, parent, child):
        states = (self._state(parent), self._state(child))
        if all(state == "assigned" for state in states):
            return "assigned"
        if all(state in ("assigned", "review") for state in states) and "review" in states:
            return "review"
        return "neutral"

    def _draw_bone(self, painter, parent, child, parent_radius, child_radius, kind):
        result = self._bone_polys(parent, child, parent_radius, child_radius)
        if not result:
            return
        polygons, outline = result
        colours = _LAYOUT["style"]["bone"][kind]
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(_qcolor(colours["lit"]))
        painter.drawPolygon(self._polygon(polygons[0]))
        painter.setBrush(_qcolor(colours["shaded"]))
        painter.drawPolygon(self._polygon(polygons[1]))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(_qcolor(_LAYOUT["style"]["boneEdge"], 0.9), 0.9,
                                  QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPolygon(self._polygon(outline))

    def _draw_joint(self, painter, role, centre, radius, state):
        style = _LAYOUT["style"]["joint"][state]
        x, y = centre.x(), centre.y()
        if state == "waiting":
            glow = QtGui.QRadialGradient(centre, radius + 9.0)
            glow.setColorAt(radius / (radius + 9.0), _qcolor("#23b7db", 0.55))
            glow.setColorAt(1.0, _qcolor("#23b7db", 0.0))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(centre, radius + 9.0, radius + 9.0)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(_qcolor("#4cc8e6", 0.95), 1.3))
            painter.drawEllipse(centre, radius + 4.0, radius + 4.0)
        draw_radius = radius * 1.12 if role == self.hovered else radius
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(_qcolor("#16191b", 0.55))
        painter.drawEllipse(QtCore.QPointF(x, y + 0.8), draw_radius + 1.6, draw_radius + 1.6)
        gradient = QtGui.QRadialGradient(QtCore.QPointF(x, y), draw_radius,
                                         QtCore.QPointF(x - draw_radius * 0.38,
                                                        y - draw_radius * 0.42))
        gradient.setColorAt(0.0, _qcolor(style["highlight"]))
        gradient.setColorAt(0.55, _qcolor(style["base"]))
        gradient.setColorAt(1.0, _qcolor(style["shadow"]))
        painter.setBrush(gradient)
        painter.setPen(QtGui.QPen(_qcolor(style["ring"]), style["ringWidthPx"]))
        painter.drawEllipse(centre, draw_radius, draw_radius)
        if draw_radius >= 5.5 and state != "required":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(_qcolor("#ffffff", 0.16), 0.9))
            painter.drawEllipse(centre, draw_radius * 0.9, draw_radius * 0.3)
        if state == "required":
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(_qcolor("#d9534f", 0.9))
            painter.drawEllipse(centre, draw_radius * 0.28, draw_radius * 0.28)
        if role == self.hovered:
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(_qcolor("#ffffff", 0.85), 1.3))
            painter.drawEllipse(centre, draw_radius + 3.2, draw_radius + 3.2)
        if self.hands and role[-1:].isdigit() and draw_radius >= 7.5:
            font = _font(_LAYOUT["style"]["label"], max(8, int(draw_radius * 1.05)), QtGui.QFont.DemiBold)
            painter.setFont(font)
            dark_text = state in ("assigned", "review", "waiting", "invalid")
            painter.setPen(_qcolor("#14251a" if dark_text else "#dfe5e8", 0.85 if dark_text else 0.8))
            painter.drawText(QtCore.QRectF(x - draw_radius, y - draw_radius,
                                           2 * draw_radius, 2 * draw_radius),
                             QtCore.Qt.AlignCenter, role[-1])

    @staticmethod
    def _label_rect(font_metrics, anchor, x, y):
        width = font_metrics.horizontalAdvance(anchor["text"])
        height = font_metrics.height()
        align = anchor.get("align", "center")
        left = x if align == "left" else x - width if align == "right" else x - width / 2.0
        return QtCore.QRectF(left, y - height / 2.0, width, height)

    def _draw_labels(self, painter, scale, ox, oy):
        view = _LAYOUT[self._view_name()]
        label_style = _LAYOUT["style"]["label"]
        for role, anchor_data in view.get("labels", {}).items():
            if scale < anchor_data.get("minScale", 0):
                continue
            anchor = anchor_data
            compact = anchor_data.get("compact")
            if compact and scale < compact.get("below", 0):
                anchor = dict(compact, text=anchor_data["text"])
            required = self.hands or view["joints"].get(role, {}).get("required", False) or role in REQUIRED_ROLES
            size = label_style["requiredPx"] if required else label_style["optionalPx"]
            font = _font(label_style, size)
            painter.setFont(font)
            metrics = QtGui.QFontMetricsF(font)
            x, y = ox + anchor["x"] * scale, oy + anchor["y"] * scale
            rect = self._label_rect(metrics, anchor, x, y)
            state = self._state(role) if role in view["joints"] else None
            colour = label_style["required"] if required else label_style["optional"]
            if state == "required":
                colour = label_style["requiredEmpty"]
            elif state == "waiting":
                colour = label_style["waiting"]
            painter.setPen(_qcolor(colour))
            painter.drawText(rect, QtCore.Qt.AlignCenter, anchor["text"])
        heading_style = _LAYOUT["style"]["label"]
        heading_font = _font(heading_style, heading_style.get("headingPx", 10),
                             QtGui.QFont.DemiBold, heading_style.get("headingLetterSpacingPx", 0))
        painter.setFont(heading_font)
        painter.setPen(_qcolor(heading_style["heading"]))
        metrics = QtGui.QFontMetricsF(heading_font)
        for heading in view.get("headings", []):
            x, y = ox + heading["x"] * scale, oy + heading["y"] * scale
            painter.drawText(self._label_rect(metrics, dict(heading, text=heading["text"]), x, y),
                             QtCore.Qt.AlignCenter, heading["text"])

    def paintEvent(self, event):
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        view_name = self._view_name()
        view = _LAYOUT[view_name]
        scale, ox, oy = self._transform()
        target = QtCore.QRectF(ox, oy, _LAYOUT["viewBox"][2] * scale, _LAYOUT["viewBox"][3] * scale)
        self._renderers[view_name].render(painter, target)
        centres = {role: self._screen_point(role) for role in view["joints"]}
        radii = {role: self._radius(role, scale) for role in view["joints"]}
        for parent, child in view.get("bones", []):
            self._draw_bone(painter, centres[parent], centres[child], radii[parent], radii[child],
                            self._bone_kind(parent, child))
        waiting = self.waiting
        for role in view["joints"]:
            if role != waiting:
                self._draw_joint(painter, role, centres[role], radii[role], self._state(role))
        if waiting in centres:
            self._draw_joint(painter, waiting, centres[waiting], radii[waiting], "waiting")
        self._draw_labels(painter, scale, ox, oy)
        painter.end()
