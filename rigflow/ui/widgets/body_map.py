"""HumanIK-style definition map rendered from the checked-in art layout.

The SVGs contain only the mannequin silhouettes. Coordinates, bones, labels,
colours and state sizes live in ``assets/definition/layout.json`` so the art
can be regenerated without a second coordinate table in Python.
"""
from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

from rigflow.skeleton.roles import REQUIRED_ROLES, display_name, parse_role, role_name
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


def body_layout(roles=()):
    """Independent body geometry for the roles present on one model.

    Only canonical spine/neck roles change the template. Helpers and roles on
    the other model cannot add slots here. Default spine slots remain available
    even when the rig has fewer joints or a definition is cleared.
    """
    counts = {"Spine": 4, "Neck": 1}
    for role in roles:
        parsed = parse_role(role)
        if parsed and parsed[1] in counts:
            counts[parsed[1]] = max(counts[parsed[1]], parsed[2] + 1)
    view = deepcopy(_LAYOUT["body"])
    joints = view["joints"]
    hips, chest, head = (dict(joints[r]) for r in ("Hips", "Spine3", "Head"))
    for part, count in counts.items():
        start, end = (hips, chest) if part == "Spine" else (chest, head)
        template = dict(joints[part])
        for i in range(count):
            role = role_name(part, index=i)
            t = (i + 1) / float(count if part == "Spine" else count + 1)
            item = dict(template, x=start["x"] + (end["x"] - start["x"]) * t,
                        y=start["y"] + (end["y"] - start["y"]) * t,
                        required=role in REQUIRED_ROLES)
            if count == (4 if part == "Spine" else 1):
                item = dict(_LAYOUT["body"]["joints"][role])
            if not item["required"]:
                item["r"] = _LAYOUT["body"]["joints"]["Spine1"]["r"]
            joints[role] = item
            label = dict(view["labels"].get(role, view["labels"][part]))
            leader = [list(p) for p in label["leader"]]
            leader[-1] = [item["x"], item["y"]]
            if count > (4 if part == "Spine" else 1):
                label["y"] = item["y"]
                leader[0][1] = leader[1][1] = item["y"]
            view["labels"][role] = dict(label, text=display_name(role), leader=leader)
    chain = (["Hips"] + [role_name("Spine", index=i) for i in range(counts["Spine"])] +
             [role_name("Neck", index=i) for i in range(counts["Neck"])] + ["Head"])
    view["bones"] = list(zip(chain, chain[1:])) + [
        [role_name("Spine", index=counts["Spine"] - 1) if a == "Spine3" else a, b]
        for a, b in view["bones"] if a not in chain or b not in chain]
    return view


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
    background_clicked = Signal()

    def __init__(self, parent=None, show_labels=True):
        super().__init__(parent)
        self.show_labels = show_labels
        self.hands = False
        self.states, self.joints = {}, {}
        self.waiting = None
        self.hovered = None
        self.selected_role = None
        self._body_roles = frozenset()
        self._body_layout = body_layout()
        self.setMouseTracking(True)
        self.setMinimumSize(500 if show_labels else 330, 250)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setAccessibleName("Character definition body map")
        self._renderers = {}
        for view in ("body", "hands"):
            svg_path = _DEFINITION_DIR / _LAYOUT[view]["svg"]
            self._renderers[view] = QtSvg.QSvgRenderer(str(svg_path), self)

    @property
    def slots(self):
        return {role: (item["x"], item["y"]) for role, item in self._view()["joints"].items()}

    @property
    def definition_roles(self):
        return set(self._body_layout["joints"]) | set(hand_slots())

    def set_roles(self, roles):
        """Use this side's labeling and populated mapping roles for its chains."""
        roles = frozenset(r for r in roles if r.startswith(("Spine", "Neck")))
        if roles != self._body_roles:
            self._body_roles = roles
            self._body_layout = body_layout(roles)
            if self.hovered not in self.slots:
                self.hovered = None
                self.setToolTip("")
            self.update()

    def _view(self):
        return _LAYOUT["hands"] if self.hands else self._body_layout

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
        left, top = 0.0, 0.0
        if not self.show_labels:
            # Fit the silhouette and joint padding, excluding the label columns.
            joints = _LAYOUT[self._view_name()]["joints"].values()
            left = max(0, min(j["x"] - j["r"] for j in joints) - 55)
            right = min(width, max(j["x"] + j["r"] for j in joints) + 55)
            top = max(0, min(j["y"] - j["r"] for j in joints) - 55)
            bottom = min(height, max(j["y"] + j["r"] for j in joints) + 55)
            width, height = right - left, bottom - top
        scale = min(self.width() / float(width), self.height() / float(height))
        return scale, (self.width() - width * scale) / 2.0 - left * scale, (self.height() - height * scale) / 2.0 - top * scale

    def _screen_point(self, role):
        scale, ox, oy = self._transform()
        item = self._view()["joints"][role]
        return QtCore.QPointF(ox + item["x"] * scale, oy + item["y"] * scale)

    def _radius(self, role, scale=None):
        view = self._view_name()
        scale = self._transform()[0] if scale is None else scale
        item = self._view()["joints"][role]
        minima = _LAYOUT["style"]["jointMinRadiusPx"][view]
        radius = max(float(minima["required" if item.get("required") else "optional"]), item["r"] * scale)
        clearance = self._chain_clearance(role, scale)
        return min(radius, clearance * 0.30) if clearance is not None else radius

    def _chain_clearance(self, role, scale):
        if self.hands or not (role in ("Hips", "Head") or role.startswith(("Spine", "Neck"))):
            return None
        return self._slot_clearance(role, scale)

    def _slot_clearance(self, role, scale):
        if self.hands:
            return None
        items = self._view()["joints"]
        item = items[role]
        return min(math.hypot(item["x"] - other["x"], item["y"] - other["y"]) * scale
                   for name, other in items.items() if name != role)

    def _hit_radius(self, role, scale=None):
        scale = self._transform()[0] if scale is None else scale
        radius = max(self._radius(role, scale) + 4.0, 10.0)
        clearance = self._slot_clearance(role, scale)
        return min(radius, clearance * 0.46) if clearance is not None else radius

    def slot_position(self, role):
        point = self._screen_point(role)
        return QtCore.QPoint(round(point.x()), round(point.y()))

    def role_at(self, position):
        point = QtCore.QPointF(position)
        scale = self._transform()[0]
        # At small sizes nearby slots have overlapping hit areas; choose nearest.
        for role in sorted(self.slots, key=lambda r: (self._screen_point(r).x() - point.x()) ** 2 + (self._screen_point(r).y() - point.y()) ** 2):
            centre = self._screen_point(role)
            hit = self._hit_radius(role, scale)
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
        elif event.button() == QtCore.Qt.LeftButton:
            self.background_clicked.emit()
        event.accept()

    def mouseMoveEvent(self, event):
        role = self.role_at(event.pos())
        if role != self.hovered:
            self.hovered = role
            self.setCursor(QtCore.Qt.PointingHandCursor if role else QtCore.Qt.ArrowCursor)
            if role:
                required = self._view()["joints"][role].get("required", False)
                status = "Required" if required or role in REQUIRED_ROLES else "Optional"
                self.setToolTip("{} · {}\n{}".format(
                    display_name(role).replace("Fore Arm", "Forearm"), self.joints.get(role) or "not connected", status))
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
        view = self._view()
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
        clearance = self._chain_clearance(role, self._transform()[0])
        halo = min(3.2, max(0.0, clearance * 0.46 - radius)) if clearance is not None else 3.2
        if state == "waiting":
            glow_size = min(9.0, halo * 2) if clearance is not None else 9.0
            glow = QtGui.QRadialGradient(centre, radius + glow_size)
            glow.setColorAt(radius / (radius + glow_size), _qcolor("#23b7db", 0.55))
            glow.setColorAt(1.0, _qcolor("#23b7db", 0.0))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(centre, radius + glow_size, radius + glow_size)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(_qcolor("#4cc8e6", 0.95), 1.3))
            painter.drawEllipse(centre, radius + halo, radius + halo)
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
            painter.drawEllipse(centre, radius + halo, radius + halo)
        if role == self.selected_role:
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(_qcolor("#23b7db"), 1.3))
            painter.drawEllipse(centre, radius + halo, radius + halo)
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

    def _visible_labels(self, scale):
        """Share label visibility and compact anchors with their leaders."""
        for role, data in self._view().get("labels", {}).items():
            if scale < data.get("minScale", 0):
                continue
            compact = data.get("compact")
            anchor = dict(compact, text=data["text"]) if compact and scale < compact.get("below", 0) else data
            yield role, anchor

    def _label_style(self, role):
        view = self._view()
        style = _LAYOUT["style"]["label"]
        required = self.hands or view["joints"].get(role, {}).get("required", False) or role in REQUIRED_ROLES
        colour = style["required"] if required else style["optional"]
        state = self._state(role) if role in view["joints"] else None
        if state == "required":
            colour = style["requiredEmpty"]
        elif state == "waiting":
            colour = style["waiting"]
        return style["requiredPx"] if required else style["optionalPx"], colour

    def _draw_leaders(self, painter, scale, ox, oy):
        style = _LAYOUT["style"].get("leader", {})
        for role, anchor in self._visible_labels(scale):
            points = anchor.get("leader")
            if not points:
                continue
            _, colour = self._label_style(role)
            hot = self._state(role) == "waiting" or role == self.hovered
            opacity = style.get("hotOpacity", 0.9) if hot else style.get("opacity", 0.38)
            painter.setPen(QtGui.QPen(_qcolor(colour, opacity), style.get("widthPx", 1.0),
                                      QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawPolyline(self._polygon([
                QtCore.QPointF(ox + x * scale, oy + y * scale) for x, y in points]))

    def _draw_labels(self, painter, scale, ox, oy):
        view = self._view()
        label_style = _LAYOUT["style"]["label"]
        for role, anchor in self._visible_labels(scale):
            size, colour = self._label_style(role)
            font = _font(label_style, size)
            painter.setFont(font)
            metrics = QtGui.QFontMetricsF(font)
            x, y = ox + anchor["x"] * scale, oy + anchor["y"] * scale
            rect = self._label_rect(metrics, anchor, x, y)
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
        view = self._view()
        scale, ox, oy = self._transform()
        target = QtCore.QRectF(ox, oy, _LAYOUT["viewBox"][2] * scale, _LAYOUT["viewBox"][3] * scale)
        self._renderers[view_name].render(painter, target)
        if self.show_labels:
            self._draw_leaders(painter, scale, ox, oy)
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
        if self.show_labels:
            self._draw_labels(painter, scale, ox, oy)
        else:
            painter.setFont(_font(_LAYOUT["style"]["label"], 10))
            painter.setPen(_qcolor("#a0a0a0"))
            painter.drawText(QtCore.QRectF(12, 10, 20, 16), QtCore.Qt.AlignCenter, "R")
            painter.drawText(QtCore.QRectF(self.width() - 32, 10, 20, 16), QtCore.Qt.AlignCenter, "L")
        painter.end()
