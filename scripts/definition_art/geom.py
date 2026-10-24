"""RigFlow character-definition art: silhouettes, joints, bones and labels.

Everything is in SVG viewBox units (1000 x 640). Run gen.py to write the assets.
"""
import math

W, H = 1000, 640
CX = 500.0


def mirror_x(p):
    return (2 * CX - p[0], p[1]) + tuple(p[2:])


# --------------------------------------------------------------------------- splines

def catmull_path(points, closed=True, tension=1.0):
    """Closed Catmull-Rom spline through points -> SVG path data.

    A point (x, y, 'c') is a corner: its tangent collapses so the curve meets it
    at an angle (crotch, armpit, finger webs).
    """
    n = len(points)
    pts = [(float(p[0]), float(p[1])) for p in points]
    corner = [len(p) > 2 and p[2] == 'c' for p in points]

    def tangent(i):
        if corner[i % n]:
            return (0.0, 0.0)
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        return ((b[0] - a[0]) * tension / 6.0, (b[1] - a[1]) * tension / 6.0)

    d = ["M%.2f,%.2f" % pts[0]]
    segs = n if closed else n - 1
    for i in range(segs):
        p1, p2 = pts[i % n], pts[(i + 1) % n]
        t1, t2 = tangent(i), tangent(i + 1)
        c1 = (p1[0] + t1[0], p1[1] + t1[1])
        c2 = (p2[0] - t2[0], p2[1] - t2[1])
        d.append("C%.2f,%.2f %.2f,%.2f %.2f,%.2f" % (c1 + c2 + p2))
    if closed:
        d.append("Z")
    return " ".join(d)


def sample_catmull(points, closed=True, tension=1.0, steps=12):
    """Polyline sampling of the same spline (for collision tests)."""
    n = len(points)
    pts = [(float(p[0]), float(p[1])) for p in points]
    corner = [len(p) > 2 and p[2] == 'c' for p in points]

    def tangent(i):
        if corner[i % n]:
            return (0.0, 0.0)
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        return ((b[0] - a[0]) * tension / 6.0, (b[1] - a[1]) * tension / 6.0)

    out = []
    for i in range(n if closed else n - 1):
        p1, p2 = pts[i % n], pts[(i + 1) % n]
        t1, t2 = tangent(i), tangent(i + 1)
        c1 = (p1[0] + t1[0], p1[1] + t1[1])
        c2 = (p2[0] - t2[0], p2[1] - t2[1])
        for s in range(steps):
            t = s / float(steps)
            mt = 1 - t
            x = mt ** 3 * p1[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p2[0]
            y = mt ** 3 * p1[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p2[1]
            out.append((x, y))
    return out


# --------------------------------------------------------------------------- body

# Screen-right half of the mannequin (the character's LEFT side), clockwise from
# the crown to the crotch. Head height 80 units; floor at y=630 -> ~7.6 heads.
BODY_HALF = [
    (500, 16),
    (516, 18), (527, 25.5), (531.5, 38), (532.5, 50),                       # cranium
    (535, 55.5), (536, 62.5), (533, 70, 'c'),                               # ear
    (528, 77.5), (522, 87.5), (518.5, 93.5, 'c'),                           # jaw -> under the jaw
    (519.5, 100.5), (523, 106.5),                                           # neck side
    (531, 109.5), (547, 112.5), (565, 117.5), (580, 120.5),                 # trapezius
    (593, 121), (606, 122.8), (618, 124.5),                                 # deltoid cap
    (648, 125.2), (680, 126.5), (698, 128.5),                               # upper arm (top)
    (717, 128), (745, 129.5), (772, 132), (787, 133.5),                     # forearm -> wrist
    (802, 132.2), (824, 131.6), (846, 133.6), (861, 136.6),                 # back of the hand
    (870, 141), (871, 145.2), (866.5, 148.6), (851, 150.2), (838, 150.6),   # finger tips
    (832, 151.4, 'c'), (827, 155.6), (815, 158.2), (802, 157.4),            # thumb
    (792, 153.8), (786, 152),                                               # wrist (under)
    (770, 154.8), (743, 158), (716, 158.6), (698, 156.4),                   # forearm (under)
    (676, 158), (646, 160), (618, 161.6), (598, 163), (586, 165, 'c'),      # upper arm (under) -> armpit
    (581, 176), (578.5, 195), (574, 215), (568.5, 234),                     # lat -> waist
    (566, 250), (567.5, 266), (572.5, 285), (577.5, 305),                   # iliac crest -> hip
    (580, 326), (579, 352), (574.5, 384), (569, 418),                       # outer thigh
    (566, 441), (567.5, 459), (572.5, 482), (574.5, 506),                   # knee -> calf
    (571, 532), (565.5, 556), (563.5, 574),                                 # shin -> ankle
    (568, 586), (575, 600), (580.5, 613), (578.5, 624), (568, 629.5),       # foot (outer) -> toes
    (552, 630.5), (541, 627.5), (538, 616), (539.5, 601),                   # foot (inner)
    (542, 586), (541, 571),                                                 # inner ankle
    (536.5, 548), (530.5, 514), (529, 484), (531.5, 458),                   # calf (inner) -> knee
    (530, 436), (525, 404), (517, 372), (509, 349), (500, 338, 'c'),        # inner thigh -> crotch
]


def body_outline():
    right = BODY_HALF
    left = [mirror_x(p) for p in reversed(right[1:-1])]
    return right + left


# Very quiet anatomy lines: open polylines (stroked only).
def body_details():
    lines = []
    for s in (1, -1):
        X = lambda x: CX + s * (x - CX)
        lines += [
            [(X(510), 200), (X(530), 203.5), (X(552), 199.5), (X(568), 188)],      # pectoral
            [(X(548), 287), (X(530), 309), (X(512), 326)],                          # inguinal
        ]
    return lines


BODY_JOINTS = {
    "Head": (500, 74), "Neck": (500, 118),
    "Spine3": (500, 154), "Spine2": (500, 190), "Spine1": (500, 227),
    "Spine": (500, 263), "Hips": (500, 299),
}
for _side, _s in (("Left", 1), ("Right", -1)):
    for _part, _x, _y in (("Shoulder", 541, 136), ("Arm", 584, 140), ("ForeArm", 697, 142),
                          ("Hand", 791, 143), ("UpLeg", 545, 316), ("Leg", 549, 452),
                          ("Foot", 553, 576), ("ToeBase", 562, 612)):
        BODY_JOINTS[_side + _part] = (CX + _s * (_x - CX), _y)

BODY_BONES = [("Hips", "Spine"), ("Spine", "Spine1"), ("Spine1", "Spine2"), ("Spine2", "Spine3"),
              ("Spine3", "Neck"), ("Neck", "Head")]
for _side in ("Left", "Right"):
    BODY_BONES += [("Spine3", _side + "Shoulder"), (_side + "Shoulder", _side + "Arm"),
                   (_side + "Arm", _side + "ForeArm"), (_side + "ForeArm", _side + "Hand"),
                   ("Hips", _side + "UpLeg"), (_side + "UpLeg", _side + "Leg"),
                   (_side + "Leg", _side + "Foot"), (_side + "Foot", _side + "ToeBase")]

# Label anchors: (x, y, align, text) where align is left/right/center and y is the
# text's vertical centre. Screen-right values are mirrored for the character's right.
BODY_LABELS = {
    "Head": (541, 50, "left", "Head"),
    "Neck": (513, 119, "left", "Neck"),
    "Spine3": (520, 161, "left", "Spine 3"),
    "Spine2": (520, 190, "left", "Spine 2"),
    "Spine1": (520, 227, "left", "Spine 1"),
    "Spine": (522, 263, "left", "Spine"),
    "Hips": (522, 285, "left", "Hips"),
}
_SIDE_LABELS = {
    "Shoulder": (529, 99.5, "left", "Shoulder"),
    "Arm": (600, 104, "center", "Arm"),
    "ForeArm": (697, 109, "center", "Forearm"),
    "Hand": (800, 110, "center", "Hand"),
    "UpLeg": (594, 316, "left", "Up Leg"),
    "Leg": (584, 452, "left", "Leg"),
    "Foot": (582, 576, "left", "Foot"),
    "ToeBase": (594, 612, "left", "Toe"),
}
_FLIP = {"left": "right", "right": "left", "center": "center"}
for _part, (_x, _y, _a, _t) in _SIDE_LABELS.items():
    BODY_LABELS["Left" + _part] = (_x, _y, _a, _t)
    BODY_LABELS["Right" + _part] = (2 * CX - _x, _y, _FLIP[_a], _t)

# Alternative anchors used below scale 0.7, where pixel-sized text no longer fits
# inside the torso.
BODY_COMPACT = {"Spine": (578, 251, "left"), "Hips": (585, 283, "left")}

BODY_HEADINGS = [("RIGHT", 210, 52, "center"), ("LEFT", 790, 52, "center")]


# --------------------------------------------------------------------------- hands

def _v(a, b):
    return (b[0] - a[0], b[1] - a[1])


def _unit(v):
    l = math.hypot(*v)
    return (v[0] / l, v[1] / l)


# Left hand, palm towards the viewer, fingers up, on the screen-right; the thumb
# points to the centre. The right hand is its mirror image.
# finger: base knuckle (joint 1), angle from vertical in degrees (+ = toward pinky),
# phalanx lengths, half widths (at knuckle 1, 2, 3 and tip).
FINGERS = {
    "Index":  dict(base=(661, 350), ang=-6.0, ph=(106, 67, 53), w=(23.5, 20.5, 18.5, 15.5)),
    "Middle": dict(base=(719, 338), ang=-0.5, ph=(117, 74, 58), w=(24.5, 21.5, 19.0, 16.0)),
    "Ring":   dict(base=(775, 346), ang=5.5, ph=(109, 68, 55), w=(23.0, 20.0, 18.0, 15.0)),
    "Pinky":  dict(base=(826, 370), ang=13.0, ph=(86, 52, 45), w=(20.0, 17.0, 15.5, 13.0)),
}
WEB = 0.42          # finger web height, as a fraction of the proximal phalanx


def finger_frame(f):
    a = math.radians(f["ang"])
    u = (math.sin(a), -math.cos(a))            # along the finger (up)
    n = (-u[1], u[0])                          # to the pinky side
    return u, n


def finger_joints(f):
    u, _ = finger_frame(f)
    b = f["base"]
    out, t = [b], 0.0
    for L in f["ph"][:2]:
        t += L
        out.append((b[0] + u[0] * t, b[1] + u[1] * t))
    return out


def finger_side(f, side):
    """Points up one side of a finger (side=-1 thumb side, +1 pinky side), from the web."""
    u, n = finger_frame(f)
    b = f["base"]
    p1, p2, p3 = f["ph"]
    w1, w2, w3, wt = f["w"]
    # (t along finger, half width): pads between creases bulge slightly.
    prof = [(p1 * WEB, w1 - 0.5), (p1 * .72, w1 - 1.2), (p1, w2 + 0.6), (p1 + p2 * .5, w2 - 0.7),
            (p1 + p2, w3 + 0.5), (p1 + p2 + p3 * .45, w3 - 0.3), (p1 + p2 + p3 - wt * 0.9, wt)]
    pts = []
    for t, w in prof:
        pts.append((b[0] + u[0] * t + n[0] * w * side, b[1] + u[1] * t + n[1] * w * side))
    return pts


def finger_tip(f):
    u, n = finger_frame(f)
    b = f["base"]
    L = sum(f["ph"])
    wt = f["w"][3]
    c = (b[0] + u[0] * (L - wt), b[1] + u[1] * (L - wt))
    pts = []
    for deg in (-55, -25, 0, 25, 55):          # around the rounded tip, thumb side -> pinky side
        a = math.radians(deg)
        d = (u[0] * math.cos(a) + n[0] * math.sin(a), u[1] * math.cos(a) + n[1] * math.sin(a))
        r = wt * (1.0 if deg == 0 else 0.98)
        pts.append((c[0] + d[0] * r, c[1] + d[1] * r))
    return pts


THUMB = dict(cmc=(676, 514), mcp=(624, 448), ip=(587, 395), tip_len=57)
# stations along the thumb axis: (segment index, fraction, outer half width, inner half width)
THUMB_PROFILE = [(0, 0.0, 45, None), (0, 0.45, 37, None), (0, 0.82, 27.5, None), (1, 0.0, 24.5, None),
                 (1, 0.5, 21.0, 19.8), (2, 0.0, 21.8, 20.6), (2, 0.42, 20.6, 19.6)]


def thumb_joints():
    return [THUMB["cmc"], THUMB["mcp"], THUMB["ip"]]


def _thumb_axis():
    cmc, mcp, ip = thumb_joints()
    u = _unit(_v(mcp, ip))
    tip = (ip[0] + u[0] * THUMB["tip_len"], ip[1] + u[1] * THUMB["tip_len"])
    return [cmc, mcp, ip, tip]


def _thumb_station(seg, frac, w, side):
    axis = _thumb_axis()
    a, b = axis[seg], axis[seg + 1]
    u = _unit(_v(a, b))
    if frac == 0.0 and seg > 0:                     # average the direction at a knuckle
        u0 = _unit(_v(axis[seg - 1], a))
        u = _unit((u[0] + u0[0], u[1] + u0[1]))
    n = (u[1], -u[0])                               # outer side (away from the index)
    p = (a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac)
    return (p[0] + n[0] * w * side, p[1] + n[1] * w * side)


def hand_outline_left():
    pts = []
    # forearm stub (radial side) -> thenar eminence -> thumb outer edge
    pts += [(653, 652), (653, 624), (655, 598), (651, 574)]
    for seg, frac, wo, wi in THUMB_PROFILE:
        pts.append(_thumb_station(seg, frac, wo, +1))
    axis = _thumb_axis()
    tip, ip = axis[3], axis[2]
    u = _unit(_v(ip, tip))
    n = (u[1], -u[0])
    rt = 17.6
    c = (tip[0] - u[0] * rt, tip[1] - u[1] * rt)
    for deg in (-62, -30, 0, 30, 62):
        a = math.radians(deg)
        d = (u[0] * math.cos(a) - n[0] * math.sin(a), u[1] * math.cos(a) - n[1] * math.sin(a))
        pts.append((c[0] + d[0] * rt, c[1] + d[1] * rt))
    for seg, frac, wo, wi in reversed(THUMB_PROFILE):
        if wi is not None:
            pts.append(_thumb_station(seg, frac, wi, -1))
    pts += [(631, 424.5), (639.5, 433), (644.5, 426), (643.5, 408), (640.5, 388)]   # thumb-index web
    order = ["Index", "Middle", "Ring", "Pinky"]
    for i, name in enumerate(order):
        f = FINGERS[name]
        left_side = finger_side(f, -1)
        if i > 0:
            left_side = left_side[1:]
        pts += left_side
        pts += finger_tip(f)
        right_side = list(reversed(finger_side(f, +1)))
        if i < len(order) - 1:
            nxt = FINGERS[order[i + 1]]
            a = right_side[-1]
            b = finger_side(nxt, -1)[0]
            valley = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 7)
            pts += right_side[:-1] + [valley]
        else:
            pts += right_side[:-1]          # the pinky blends into the hypothenar edge
    # ulnar edge (hypothenar) down to the wrist and forearm
    pts += [(851.5, 352), (855, 392), (859, 428), (861, 464), (856, 506), (844, 545), (830, 577), (822, 602), (821, 627), (821, 652)]
    return pts


HAND_JOINTS = {}
HAND_BONES = []
for _side, _s in (("Left", 1), ("Right", -1)):
    _m = lambda p, s=_s: (CX + s * (p[0] - CX), p[1])
    _wrist = _side + "Hand"
    HAND_JOINTS[_wrist] = _m((736, 570))
    for _name, _f in FINGERS.items():
        for _i, _p in enumerate(finger_joints(_f), 1):
            HAND_JOINTS["%sHand%s%d" % (_side, _name, _i)] = _m(_p)
    for _i, _p in enumerate(thumb_joints(), 1):
        HAND_JOINTS["%sHandThumb%d" % (_side, _i)] = _m(_p)
    for _name in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        _r = "%sHand%s" % (_side, _name)
        HAND_BONES += [(_wrist, _r + "1"), (_r + "1", _r + "2"), (_r + "2", _r + "3")]


def _finger_label_pos(name):
    if name == "Thumb":
        tip = _thumb_axis()[3]
        return (tip[0] + 10, tip[1] - 26)
    f = FINGERS[name]
    u, _ = finger_frame(f)
    L = sum(f["ph"]) + 22
    return (f["base"][0] + u[0] * L, f["base"][1] + u[1] * L)


HAND_LABELS = {}
for _side, _s in (("Left", 1), ("Right", -1)):
    for _name in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        x, y = _finger_label_pos(_name)
        HAND_LABELS["%sHand%s" % (_side, _name)] = (CX + _s * (x - CX), y, "center", _name)
    HAND_LABELS[_side + "Hand"] = (CX + _s * (736 - CX), 604, "center", "Wrist")
HAND_HEADINGS = [("RIGHT HAND", 40, 36, "left"), ("LEFT HAND", 960, 36, "right")]

REQUIRED = {"Hips", "Spine", "Head", "LeftArm", "LeftForeArm", "LeftHand", "RightArm", "RightForeArm",
            "RightHand", "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot"}
