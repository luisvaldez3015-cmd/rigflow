"""Painted character-definition body and hands; all coordinates are logical units."""
from rigflow.skeleton.roles import REQUIRED_ROLES, display_name
from rigflow.ui import theme
from rigflow.ui.qt import QtCore, QtGui, QtWidgets, Signal


BODY_SLOTS = {"Head": (400, 44), "Neck": (400, 86), "Spine3": (400, 116),
              "Spine2": (400, 143), "Spine1": (400, 170), "Spine": (400, 197), "Hips": (400, 231)}
for _side, _sign in (("Left", 1), ("Right", -1)):
    for _part, _x, _y in (("Shoulder", 38, 107), ("Arm", 88, 117), ("ForeArm", 163, 155),
                         ("Hand", 233, 191), ("UpLeg", 41, 249), ("Leg", 48, 310),
                         ("Foot", 52, 370), ("ToeBase", 68, 395)):
        BODY_SLOTS[_side + _part] = (400 + _sign * _x * 1.35, _y)


def hand_slots():
    slots = {}
    for side, center, sign in (("Right", 205, -1), ("Left", 595, 1)):
        slots[side + "Hand"] = (center, 348)
        for finger, dx, tip in (("Thumb", -120, 222), ("Index", -62, 105),
                                ("Middle", -15, 78), ("Ring", 32, 103), ("Pinky", 79, 149)):
            for index in range(1, 4):
                x = center + sign * (dx * (.65 + index * .35 / 3))
                y = 285 + (tip - 285) * index / 3
                slots[side + "Hand" + finger + str(index)] = (x, y)
    return slots


class BodyMap(QtWidgets.QWidget):
    """Clickable slots with a shared hit-test for painting, GUI checks and tests."""
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

    @property
    def slots(self):
        return hand_slots() if self.hands else BODY_SLOTS

    def set_hands(self, enabled):
        self.hands = enabled
        self.hovered = None
        self.update()

    def _transform(self):
        scale = min(self.width() / 800.0, self.height() / 420.0)
        return scale, (self.width() - 800 * scale) / 2, (self.height() - 420 * scale) / 2

    def slot_position(self, role):
        scale, x, y = self._transform()
        px, py = self.slots[role]
        return QtCore.QPoint(round(x + px * scale), round(y + py * scale))

    def role_at(self, position):
        for role in self.slots:
            point = self.slot_position(role)
            if (point.x() - position.x()) ** 2 + (point.y() - position.y()) ** 2 <= 14 ** 2:
                return role

    def mousePressEvent(self, event):
        role = self.role_at(event.pos())
        if role:
            if event.button() == QtCore.Qt.RightButton:
                self.slot_menu.emit(role, event.globalPos())
            elif event.button() == QtCore.Qt.LeftButton:
                self.slot_clicked.emit(role)

    def mouseMoveEvent(self, event):
        role = self.role_at(event.pos())
        if role != self.hovered:
            self.hovered = role
            self.setCursor(QtCore.Qt.PointingHandCursor if role else QtCore.Qt.ArrowCursor)
            self.setToolTip((display_name(role) + (" · Required" if role in REQUIRED_ROLES else " · Optional") +
                             "\n" + (self.joints.get(role) or "Click, then select a joint in Maya")) if role else "")
            self.update()

    def leaveEvent(self, event):
        self.hovered = None
        self.update()
        super().leaveEvent(event)

    def _line(self, painter, points, color, width):
        painter.setPen(QtGui.QPen(QtGui.QColor(color), width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(*p) for p in points]))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        scale, x, y = self._transform()
        painter.translate(x, y)
        painter.scale(scale, scale)
        painter.setPen(QtGui.QPen(QtGui.QColor(theme.BORDER_LIGHT), 1))
        painter.setBrush(QtGui.QColor("#383d40"))
        if not self.hands:
            # A quiet silhouette gives each slot an anatomical landmark.
            path = QtGui.QPainterPath()
            path.addRoundedRect(QtCore.QRectF(374, 18, 52, 55), 23, 23)
            painter.drawPath(path)
            self._line(painter, [(400, 72), (400, 100)], "#4b5357", 22)
            torso = QtGui.QPolygonF([QtCore.QPointF(*p) for p in
                [(352, 99), (448, 99), (438, 166), (430, 218), (442, 247),
                 (400, 263), (358, 247), (370, 218), (362, 166)]])
            painter.setPen(QtGui.QPen(QtGui.QColor("#515a5f"), 1))
            painter.drawPolygon(torso)
            for side in ("Left", "Right"):
                points = [BODY_SLOTS[side + part] for part in ("Shoulder", "Arm", "ForeArm", "Hand")]
                self._line(painter, points, "#515a5f", 25)
                self._line(painter, points, "#383d40", 22)
                points = [BODY_SLOTS[side + part] for part in ("UpLeg", "Leg", "Foot", "ToeBase")]
                self._line(painter, points, "#515a5f", 30)
                self._line(painter, points, "#383d40", 27)
            self._line(painter, [(400, 90), (400, 231)], "#66747a", 2)
        else:
            for side, center in (("Right", 205), ("Left", 595)):
                painter.setPen(QtGui.QPen(QtGui.QColor("#515a5f"), 1))
                painter.setBrush(QtGui.QColor("#383d40"))
                painter.drawRoundedRect(QtCore.QRectF(center - 65, 247, 130, 100), 34, 34)
                self._line(painter, [(center, 327), (center, 361)], "#515a5f", 44)
                for finger in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
                    points = [self.slots[side + "Hand" + finger + str(i)] for i in range(1, 4)]
                    self._line(painter, points, "#515a5f", 25)
                    self._line(painter, points, "#383d40", 22)
                    px, py = points[-1]
                    self._text(painter, px - 35, py - 36, 70, 20, finger, theme.MUTED)
                self._text(painter, center - 100, 382, 200, 22, side + " hand", theme.MUTED)
        for role, (px, py) in self.slots.items():
            required = role in REQUIRED_ROLES
            state = "waiting" if role == self.waiting else self.states.get(role, "required" if required else "empty")
            color = {"waiting": theme.ACCENT, "assigned": theme.GREEN, "review": theme.YELLOW,
                     "invalid": theme.RED, "required": theme.RED, "empty": "#839097"}[state]
            radius = 9 if required else (8 if self.hands else 6)
            if role == self.hovered or state == "waiting":
                painter.setPen(QtGui.QPen(QtGui.QColor(color), 1))
                painter.setBrush(QtGui.QColor("#344951"))
                painter.drawEllipse(QtCore.QPointF(px, py), radius + 5, radius + 5)
            painter.setPen(QtGui.QPen(QtGui.QColor(color), 2 if required else 1.5))
            painter.setBrush(QtGui.QColor(color if state in ("assigned", "review", "waiting", "invalid") else "#2d3235"))
            painter.drawEllipse(QtCore.QPointF(px, py), radius, radius)
            if self.hands and role[-1:].isdigit():
                self._text(painter, px - 8, py - 9, 16, 18, role[-1], "#1c292c" if state == "assigned" else theme.TEXT, 9)
            elif not self.hands:
                if role in ("Head", "Neck", "Spine3", "Spine2", "Spine1", "Spine", "Hips"):
                    self._text(painter, px + 20, py - 10, 110, 20, role, theme.TEXT if required else theme.MUTED, align=QtCore.Qt.AlignLeft)
                else:
                    label = role.replace("Left", "").replace("Right", "")
                    # Arm labels sit above; leg labels sit outside the silhouette.
                    upper = any(part in role for part in ("Shoulder", "Arm", "Hand"))
                    lx = px - 55 if upper else px + (18 if role.startswith("Left") else -128)
                    ly = py - (29 if upper else 10)
                    if "Shoulder" in role:
                        lx = 400 + (95 if role.startswith("Left") else -205)
                        ly = 66
                    self._text(painter, lx, ly, 110, 20, label, theme.TEXT if required else theme.MUTED)
        if not self.hands:
            self._text(painter, 120, 15, 170, 20, "RIGHT", theme.MUTED, 10)
            self._text(painter, 510, 15, 170, 20, "LEFT", theme.MUTED, 10)
        painter.end()

    @staticmethod
    def _text(painter, x, y, width, height, text, color, size=11, align=QtCore.Qt.AlignCenter):
        painter.setPen(QtGui.QColor(color))
        font = QtGui.QFont("Segoe UI")
        font.setPixelSize(round(size / min(1.0, painter.transform().m11())))
        painter.setFont(font)
        painter.drawText(QtCore.QRectF(x, y, width, height), align | QtCore.Qt.AlignVCenter, text)
