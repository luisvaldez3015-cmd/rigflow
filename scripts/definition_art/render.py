"""Mockups of the character-definition map, drawn per joint-style.md.

mayapy -I render.py <asset dir> <out dir>
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402
from PySide2 import QtCore, QtGui, QtSvg, QtWidgets  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets", "definition")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get("TEMP", "/tmp"), "rigflow_definition_art")
os.makedirs(OUT, exist_ok=True)
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

CARD = "#2f2f2f"

# ----------------------------------------------------------------------- joint style
from style import BONE, BONE_EDGE, JOINT as STYLE, LABEL, LEADER, MIN_PX  # noqa: E402


def color(c, a=1.0):
    q = QtGui.QColor(c)
    q.setAlphaF(a)
    return q


def joint_px(view, j, s):
    req_min, opt_min = MIN_PX[view]
    return max(req_min if j["required"] else opt_min, j["r"] * s)


def bone_polys(p, c, rp, rc):
    dx, dy = c[0] - p[0], c[1] - p[1]
    d = math.hypot(dx, dy)
    u = (dx / d, dy / d)
    n = (-u[1], u[0])
    a = min(rp * 1.25, d * 0.3)
    hw = rp * 0.62
    w1 = (p[0] + u[0] * a + n[0] * hw, p[1] + u[1] * a + n[1] * hw)
    w2 = (p[0] + u[0] * a - n[0] * hw, p[1] + u[1] * a - n[1] * hw)
    tip = (c[0] - u[0] * (rc + 1.5), c[1] - u[1] * (rc + 1.5))
    # facet facing the upper-left light is the lighter one
    light_first = (n[0] * -0.6 + n[1] * -0.8) > 0
    f1 = [p, w1, tip]
    f2 = [p, tip, w2]
    return (f1, f2) if light_first else (f2, f1), [p, w1, tip, w2]


def qpoly(pts):
    return QtGui.QPolygonF([QtCore.QPointF(*pt) for pt in pts])


def draw_bone(painter, p, c, rp, rc, kind):
    (lf, df), outline = bone_polys(p, c, rp, rc)
    light, dark = BONE[kind]
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(color(light))
    painter.drawPolygon(qpoly(lf))
    painter.setBrush(color(dark))
    painter.drawPolygon(qpoly(df))
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.setPen(QtGui.QPen(color(BONE_EDGE, 0.9), 0.9, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
    painter.drawPolygon(qpoly(outline))
    return outline


def draw_joint(painter, x, y, r, state, hovered=False, number=None):
    hi, base, sh, ring, rw = STYLE[state]
    c = QtCore.QPointF(x, y)
    if state == "waiting":
        glow = QtGui.QRadialGradient(c, r + 9)
        glow.setColorAt(r / (r + 9.0), color("#23b7db", 0.55))
        glow.setColorAt(1.0, color("#23b7db", 0.0))
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(c, r + 9, r + 9)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(color("#4cc8e6", 0.95), 1.3))
        painter.drawEllipse(c, r + 4, r + 4)
    if hovered:
        r *= 1.12
    # dark contact shadow so the sphere sits above bone and silhouette
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(color("#16191b", 0.55))
    painter.drawEllipse(QtCore.QPointF(x, y + 0.8), r + 1.6, r + 1.6)
    g = QtGui.QRadialGradient(QtCore.QPointF(x, y), r, QtCore.QPointF(x - r * .38, y - r * .42))
    g.setColorAt(0.0, color(hi))
    g.setColorAt(0.55, color(base))
    g.setColorAt(1.0, color(sh))
    painter.setBrush(g)
    painter.setPen(QtGui.QPen(color(ring), rw))
    painter.drawEllipse(c, r, r)
    # Maya-like wire latitude: a faint equator on the sphere
    if r >= 5.5 and state != "required":
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(color("#ffffff", 0.16), 0.9))
        painter.drawEllipse(c, r * 0.9, r * 0.3)
    if state == "required":
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(color("#d9534f", 0.9))
        painter.drawEllipse(c, r * 0.28, r * 0.28)
    if hovered:
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(color("#ffffff", 0.85), 1.3))
        painter.drawEllipse(c, r + 3.2, r + 3.2)
    if number is not None and r >= 7.5:
        f = QtGui.QFont("Segoe UI")
        f.setPixelSize(max(8, int(r * 1.05)))
        f.setWeight(QtGui.QFont.DemiBold)
        painter.setFont(f)
        dark_text = state in ("assigned", "review", "waiting", "invalid")
        painter.setPen(color("#14251a" if dark_text else "#dfe5e8", 0.85 if dark_text else 0.8))
        painter.drawText(QtCore.QRectF(x - r, y - r, 2 * r, 2 * r), QtCore.Qt.AlignCenter, str(number))


def font(px, weight=QtGui.QFont.Normal, spacing=0.0):
    f = QtGui.QFont("Segoe UI")
    f.setPixelSize(px)
    f.setStyleStrategy(QtGui.QFont.StyleStrategy(QtGui.QFont.PreferAntialias | QtGui.QFont.NoSubpixelAntialias))
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, spacing)
    return f


def ink_rect(fm, text, rect):
    """Tight glyph box inside a layout rect (used for collisions)."""
    t = fm.tightBoundingRect(text)
    base = rect.center().y() + (fm.ascent() - fm.descent()) / 2.0
    return QtCore.QRectF(rect.left() + t.left(), base + t.top(), t.width(), t.height())


def text_rect(fm, text, x, y, align):
    w = fm.horizontalAdvance(text)
    h = fm.height()
    if align == "left":
        left = x
    elif align == "right":
        left = x - w
    else:
        left = x - w / 2.0
    return QtCore.QRectF(left, y - h / 2.0, w, h)


# ----------------------------------------------------------------------- scene

def load():
    with open(os.path.join(ASSETS, "layout.json")) as f:
        return json.load(f)


def outlines(view):
    if view == "body":
        return [geom.sample_catmull(geom.body_outline())]
    left = geom.hand_outline_left()
    return [geom.sample_catmull([geom.mirror_x(p) for p in left]), geom.sample_catmull(left)]


def transform(w, h):
    s = min(w / 1000.0, h / 640.0)
    return s, (w - 1000 * s) / 2.0, (h - 640 * s) / 2.0


def compute_labels(view, data, w, h, required_px=11, optional_px=10):
    """Greedy placement: a label is shown only if it collides with nothing."""
    s, ox, oy = transform(w, h)
    P = lambda x, y: (ox + x * s, oy + y * s)
    paths = []
    for poly in outlines(view):
        path = QtGui.QPainterPath()
        path.addPolygon(qpoly([P(*p) for p in poly]))
        path.closeSubpath()
        paths.append(path)
    joints = data["joints"]
    jpx = {k: (P(j["x"], j["y"]), joint_px(view, j, s)) for k, j in joints.items()}
    obstacles = []
    for a, b in data["bones"]:
        (pa, ra), (pb, rb) = jpx[a], jpx[b]
        _, outline = bone_polys(pa, pb, ra, rb)
        path = QtGui.QPainterPath()
        path.addPolygon(qpoly(outline))
        path.closeSubpath()
        obstacles.append(path)
    for k, (pt, r) in jpx.items():
        path = QtGui.QPainterPath()
        rr = r + 2.5 + (9 if True else 0) * 0  # waiting halo is allowed to touch labels
        path.addEllipse(QtCore.QPointF(*pt), rr, rr)
        obstacles.append(path)
    leader_paths = {}
    stroker = QtGui.QPainterPathStroker()
    stroker.setWidth(LEADER["widthPx"] + 2.0)
    for role, lb in data["labels"].items():
        if "leader" in lb:
            lp = QtGui.QPainterPath()
            lp.addPolygon(qpoly([P(*pt) for pt in lb["leader"]]))
            leader_paths[role] = stroker.createStroke(lp)
    placed, results = [], {}
    order = sorted(data["labels"].items(), key=lambda kv: (0 if joints.get(kv[0], {}).get("required") else 1))
    # headings first
    head_font = font(10, QtGui.QFont.DemiBold, 1.6)
    hfm = QtGui.QFontMetricsF(head_font)
    for hd in data["headings"]:
        x, y = P(hd["x"], hd["y"])
        hr = text_rect(hfm, hd["text"], x, y, hd["align"])
        placed.append(ink_rect(hfm, hd["text"], hr).adjusted(-3, -3, 3, 3))
    for role, lb in order:
        req = joints.get(role, {}).get("required", False) or view == "hands"
        f = font(required_px if req else optional_px)
        fm = QtGui.QFontMetricsF(f)
        anchor = lb
        if "compact" in lb and s < lb["compact"]["below"]:
            anchor = lb["compact"]
        x, y = P(anchor["x"], anchor["y"])
        rect = text_rect(fm, lb["text"], x, y, anchor["align"])
        test = ink_rect(fm, lb["text"], rect).adjusted(-2.5, -2.5, 2.5, 2.5)
        reason = None
        if not QtCore.QRectF(0, 0, w, h).contains(test):
            reason = "canvas"
        for path in paths:
            if path.intersects(test) and not path.contains(test):
                reason = "edge"
        for ob in obstacles:
            if ob.intersects(test):
                reason = "bone/joint"
        for other in placed:
            if other.intersects(test):
                reason = "label"
        for r2, lp in leader_paths.items():
            if r2 != role and lp.intersects(test):
                reason = "leader"
        results[role] = (rect, f, reason)
        if reason is None:
            placed.append(test)
    return results


def min_scales(view, data):
    shown_at = {role: [] for role in data["labels"]}
    scales = [x / 100.0 for x in range(45, 141)]
    for sc in scales:
        res = compute_labels(view, data, 1000 * sc, 640 * sc)
        for role, (_, _, reason) in res.items():
            shown_at[role].append(reason is None)
    out = {}
    for role, flags in shown_at.items():
        m = None
        for sc, ok in reversed(list(zip(scales, flags))):
            if ok:
                m = sc
            else:
                break
        out[role] = m if m is not None else 99
        if out[role] <= scales[0]:
            out[role] = 0
    return out


def render(view, data, w, h, states, waiting, hovered, path, svg_name, number_fingers=True):
    img = QtGui.QImage(int(w), int(h), QtGui.QImage.Format_ARGB32_Premultiplied)
    img.fill(color(CARD))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setRenderHint(QtGui.QPainter.TextAntialiasing)
    p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
    s, ox, oy = transform(w, h)
    p.save()
    p.setClipRect(QtCore.QRectF(0, 0, w, h))
    QtSvg.QSvgRenderer(os.path.join(ASSETS, svg_name)).render(p, QtCore.QRectF(ox, oy, 1000 * s, 640 * s))
    p.restore()
    P = lambda x, y: (ox + x * s, oy + y * s)
    joints = data["joints"]
    jpx = {k: (P(j["x"], j["y"]), joint_px(view, j, s)) for k, j in joints.items()}

    def state_of(role):
        if role == waiting:
            return "waiting"
        return states.get(role, "required" if joints[role]["required"] else "empty")

    def label_colour(role):
        req = joints.get(role, {}).get("required", False) or view == "hands"
        st = state_of(role) if role in joints else None
        col = LABEL["required"] if req else LABEL["optional"]
        if st == "required":
            col = LABEL["requiredEmpty"]
        if st == "waiting":
            col = LABEL["waiting"]
        return col, st

    # Leaders sit under the bones and joints: they end at the joint centre and the
    # sphere covers the tip.
    for role, lb in data["labels"].items():
        if "leader" not in lb or (s < lb.get("minScale", 0) and not os.environ.get("DEBUG")):
            continue
        col, st = label_colour(role)
        hot = st == "waiting" or role == hovered
        pen = QtGui.QPen(color(col, LEADER["hotOpacity"] if hot else LEADER["opacity"]), LEADER["widthPx"])
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawPolyline(qpoly([P(*pt) for pt in lb["leader"]]))
    for a, b in data["bones"]:
        sa, sb = state_of(a), state_of(b)
        kind = "neutral"
        if sa in ("assigned", "review") and sb in ("assigned", "review"):
            kind = "review" if "review" in (sa, sb) else "assigned"
        (pa, ra), (pb, rb) = jpx[a], jpx[b]
        draw_bone(p, pa, pb, ra, rb, kind)
    for role, ((x, y), r) in jpx.items():
        num = int(role[-1]) if (view == "hands" and role[-1].isdigit() and number_fingers) else None
        draw_joint(p, x, y, r, state_of(role), hovered == role, num)
    labels = compute_labels(view, data, w, h)
    for role, (rect, f, reason) in labels.items():
        lb = data["labels"][role]
        minscale = lb.get("minScale", 0)
        if s < minscale and not os.environ.get("DEBUG"):
            continue
        req = joints.get(role, {}).get("required", False) or view == "hands"
        st = state_of(role) if role in joints else None
        col = LABEL["required"] if req else LABEL["optional"]
        if st == "required":
            col = LABEL["requiredEmpty"]
        if st == "waiting":
            col = LABEL["waiting"]
        p.setFont(f)
        p.setPen(color(col))
        p.drawText(rect, QtCore.Qt.AlignCenter, lb["text"])
        if reason:
            p.setPen(QtGui.QPen(color("#ff00ff"), 1))
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawRect(rect)
    hf = font(10, QtGui.QFont.DemiBold, 1.6)
    p.setFont(hf)
    p.setPen(color(LABEL["heading"]))
    hfm = QtGui.QFontMetricsF(hf)
    for hd in data["headings"]:
        x, y = P(hd["x"], hd["y"])
        p.drawText(text_rect(hfm, hd["text"], x, y, hd["align"]), QtCore.Qt.AlignCenter, hd["text"])
    p.end()
    img.save(path)
    bad = {r: why for r, (_, _, why) in labels.items() if why and s >= data["labels"][r].get("minScale", 0)}
    return bad


def spacing_report(view, data):
    js = data["joints"]
    worst = []
    keys = list(js)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            d = math.hypot(js[a]["x"] - js[b]["x"], js[a]["y"] - js[b]["y"])
            ratio = d / max(js[a]["r"], js[b]["r"])
            worst.append((ratio, d, a, b))
    worst.sort()
    return worst[:6]


BODY_STATES = {}
HAND_STATES = {}


def mock_states(data, view):
    st = {}
    for role, j in data["joints"].items():
        st[role] = "assigned"
    if view == "body":
        for r in ("RightFoot", "LeftLeg"):
            st[r] = "required"
        for r in ("Spine2", "LeftToeBase", "RightShoulder"):
            st[r] = "empty"
        st["Neck"] = "review"
        return st, "LeftForeArm", "Spine1"
    for r in ("LeftHandPinky3", "LeftHandRing3", "RightHandThumb3"):
        st[r] = "empty"
    st["LeftHand"] = "required"
    st["RightHandMiddle2"] = "review"
    return st, "RightHandIndex2", "LeftHandMiddle1"


if __name__ == "__main__":
    layout = load()
    sizes = {"normal": (1110, 600), "min": (910, 330)}
    report = {}
    ms_all = {}
    for view in ("body", "hands"):
        data = layout[view]
        ms_all[view] = min_scales(view, data)
        for k, v in ms_all[view].items():
            data["labels"][k]["minScale"] = v
        st, waiting, hov = mock_states(data, view)
        for size_name, (w, h) in sizes.items():
            out = os.path.join(OUT, "mock_%s_%s.png" % (view, size_name))
            bad = render(view, data, w, h, st, waiting, hov, out, data["svg"])
            report["%s/%s" % (view, size_name)] = bad
        report[view + "_spacing"] = [("%.2f" % r, "%.0f" % d, a, b) for r, d, a, b in spacing_report(view, data)]
    min_scales_path = os.environ.get("RIGFLOW_MIN_SCALES", os.path.join(OUT, "_min_scales.json"))
    with open(min_scales_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ms_all, f, indent=1)
    for k, v in report.items():
        print(k, v)
    for view, ms in ms_all.items():
        print(view, "minScale", {k: v for k, v in sorted(ms.items(), key=lambda kv: -kv[1]) if v})


def state_sheet(path, scale=2.0):
    """Every joint state at large size, plus the bone rules."""
    w, h = 900, 300
    img = QtGui.QImage(int(w * scale), int(h * scale), QtGui.QImage.Format_ARGB32_Premultiplied)
    img.fill(color(CARD))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setRenderHint(QtGui.QPainter.TextAntialiasing)
    p.scale(scale, scale)
    items = [("Assigned", "assigned", False), ("Waiting", "waiting", False), ("Review", "review", False),
             ("Required, empty", "required", False), ("Optional, empty", "empty", False),
             ("Invalid", "invalid", False), ("Hovered", "assigned", True)]
    for i, (name, st, hov) in enumerate(items):
        x = 70 + i * 125
        draw_joint(p, x, 60, 10, st, hov)
        p.setFont(font(11))
        p.setPen(color(LABEL["required"]))
        p.drawText(QtCore.QRectF(x - 60, 84, 120, 18), QtCore.Qt.AlignCenter, name)
    chains = [("Both assigned: green bone", ["assigned", "assigned", "assigned"]),
              ("Child not assigned: neutral bone", ["assigned", "empty", "required"]),
              ("Review on either end: yellow bone", ["assigned", "review", "assigned"]),
              ("Waiting child: neutral bone, glow on the joint", ["assigned", "waiting", "empty"])]
    for i, (name, sts) in enumerate(chains):
        x0 = 40 + (i % 2) * 440
        y = 160 + (i // 2) * 80
        pts = [(x0 + k * 110, y) for k in range(3)]
        radii = [10, 7 if sts[1] in ("empty",) else 10, 10]
        for k in range(2):
            a, b = sts[k], sts[k + 1]
            kind = "neutral"
            if a in ("assigned", "review") and b in ("assigned", "review"):
                kind = "review" if "review" in (a, b) else "assigned"
            draw_bone(p, pts[k], pts[k + 1], radii[k], radii[k + 1], kind)
        for k in range(3):
            draw_joint(p, pts[k][0], pts[k][1], radii[k], sts[k])
        p.setFont(font(11))
        p.setPen(color(LABEL["optional"]))
        p.drawText(QtCore.QRectF(x0 - 20, y + 18, 400, 18), QtCore.Qt.AlignLeft, name)
    p.end()
    img.save(path)


if __name__ == "__main__":
    state_sheet(os.path.join(OUT, "mock_joint_states.png"))
