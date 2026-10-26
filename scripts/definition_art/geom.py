"""RigFlow character-definition art, second pass: A-pose body and open hands.

Everything is in SVG viewBox units (1000 x 640). Run gen.py to write the assets.
The contours are drawn as Catmull-Rom control points in "design units" (a
400 x 600 drawing board for the body, another for the left hand) and mapped
into the viewBox by B() and Hd().
"""
import math

W, H = 1000, 640
CX = 500.0


def mirror_x(p):
    return (2 * CX - p[0], p[1]) + tuple(p[2:])


# --------------------------------------------------------------------------- splines

def _bezier_segments(points, closed=True, tension=1.0):
    n = len(points)
    pts = [(float(p[0]), float(p[1])) for p in points]
    corner = [len(p) > 2 and p[2] == 'c' for p in points]

    def tangent(i):
        if corner[i % n] or (not closed and i in (0, n - 1)):
            return (0.0, 0.0)
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        return ((b[0] - a[0]) * tension / 6.0, (b[1] - a[1]) * tension / 6.0)

    segs = []
    for i in range(n if closed else n - 1):
        p1, p2 = pts[i % n], pts[(i + 1) % n]
        t1, t2 = tangent(i), tangent(i + 1)
        segs.append((p1, (p1[0] + t1[0], p1[1] + t1[1]), (p2[0] - t2[0], p2[1] - t2[1]), p2))
    return segs


def catmull_path(points, closed=True, tension=1.0):
    """Catmull-Rom spline through points -> SVG path data.

    A point (x, y, 'c') is a corner: its tangent collapses so the curve meets it
    at an angle (crotch, armpit, finger webs).
    """
    segs = _bezier_segments(points, closed, tension)
    d = ["M%.2f,%.2f" % segs[0][0]]
    for _, c1, c2, p2 in segs:
        d.append("C%.2f,%.2f %.2f,%.2f %.2f,%.2f" % (c1 + c2 + p2))
    if closed:
        d.append("Z")
    return " ".join(d)


def sample_catmull(points, closed=True, tension=1.0, steps=12):
    """Polyline sampling of the same spline (for collision tests)."""
    out = []
    for p1, c1, c2, p2 in _bezier_segments(points, closed, tension):
        for s in range(steps):
            t = s / float(steps)
            mt = 1 - t
            x = mt ** 3 * p1[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p2[0]
            y = mt ** 3 * p1[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p2[1]
            out.append((x, y))
    return out


# --------------------------------------------------------------------------- body

# Body drawing board: centre line x=200, crown y=8, soles y=595 (about 8 heads,
# athletic proportions). Mapped so the figure spans y 12..632 of the viewBox.
BK = 1.054
BOX, BOY = CX - 200 * BK, 12 - 8 * BK


def B(x, y, *rest):
    return (BOX + x * BK, BOY + y * BK) + tuple(rest)


# Screen-right half of the figure (the character's LEFT side), clockwise from the
# crown to the crotch, in body design units. A-pose: arms ~25 degrees out, palms
# forward, thumbs pointing away from the body.
BODY_HALF_D = [
    (200, 8),
    (210.5, 9.5), (218.5, 15), (223.5, 24), (225.5, 35), (225, 45),                 # cranium
    (228.2, 46.2), (230.6, 50.5), (230.8, 56.5), (228.4, 61.6), (224.6, 63.6, 'c'),  # ear
    (221.4, 69), (219.6, 77), (219.4, 86), (220.6, 93.5),                           # jaw -> neck
    (225.2, 99.2), (233, 103.2), (242.6, 106.2), (252.4, 108.8), (262, 112.2),      # trapezius
    (271.4, 117.8), (279.4, 125.6), (285, 135.6), (288.4, 146.8), (289.8, 157),     # deltoid
    (292.6, 166.4), (298.4, 177.4), (304, 188.8), (308.4, 200.2),                   # upper arm (outer)
    (311.6, 211.4), (314.8, 222.6),                                                 # elbow
    (322, 233.4), (327.2, 244.2), (330.2, 255.2), (332.6, 265.6),                 # forearm -> wrist
    (339, 270), (346.6, 274.2), (354.2, 279), (360.8, 283.4), (364.8, 286.8),       # back of hand -> thumb
    (364.6, 290.2), (360.4, 291.2), (355.8, 290), (352.2, 291.4, 'c'),              # thumb tip -> web
    (356.4, 298), (360.8, 306.6), (363.6, 314), (362.8, 318.6), (359, 318.8),       # index
    (355.4, 311), (350.6, 300.4, 'c'),
    (353.4, 310), (355.8, 318.6), (354.6, 324.2), (350.6, 325.4), (347.4, 321.2),   # middle
    (344.8, 312.6), (342, 300.6, 'c'),
    (344.2, 312.6), (346.4, 320.8), (344.6, 325.2), (340.6, 324.6), (338, 316.8),   # ring
    (335.4, 302.6, 'c'),
    (336.8, 314.4), (337.2, 319.6), (334.6, 322.4), (331.2, 320.2), (329.2, 311.2),  # pinky
    (326.4, 299.6), (323, 289.4), (319.6, 280.4), (317.2, 273.4),                   # heel of the hand -> wrist
    (312, 266.4), (303.6, 257.8), (294.8, 247.6), (286.2, 236.4),                  # forearm (inner)
    (281.6, 225), (276.4, 214.4), (270.4, 203.4), (264.2, 191.6), (258.6, 179.6),   # inner elbow -> biceps
    (255.5, 169, 'c'),                                                              # armpit
    (256, 180), (255.6, 192), (254.4, 205), (252.8, 218), (251.2, 231),             # lat
    (250, 245), (249.2, 259), (249, 273), (250, 287),                               # straight flank -> iliac crest
    (251.8, 301), (254, 316), (256.2, 331), (258.2, 346),                           # hip -> outer thigh
    (259.6, 361), (260.2, 376), (259.4, 389), (257.6, 401), (255.8, 410),           # vastus
    (254.8, 422), (255.8, 435),                                                     # knee
    (258, 446), (259.6, 457), (259.8, 468), (258.8, 480), (257.2, 493),             # calf
    (255.6, 506), (254.4, 519), (253.8, 531), (254.2, 541),                         # shin -> ankle
    (256.2, 550), (260, 558), (265.4, 566), (271, 573.6), (275.4, 580.4),           # top of the foot
    (277, 585.6), (275.6, 589.2), (273.4, 590.6, 'c'),                              # little toe
    (271.8, 592.4), (268.8, 593.4), (266.6, 592.8, 'c'),                            # 4th toe
    (264.4, 594.2), (261, 594.8), (258.8, 593.8, 'c'),                              # 3rd toe
    (256.4, 594.8), (252.6, 594.6), (250.6, 593.2, 'c'),                            # 2nd toe
    (248, 593.4), (244.4, 591), (241.8, 586.4),                                     # big toe
    (239.4, 580), (237, 572.8), (235, 564.6), (233.8, 556), (233.4, 548),           # inner foot -> ankle
    (233.8, 537), (233, 524), (231.2, 511), (228.6, 497), (225.6, 483),             # inner calf
    (223.2, 470), (222.2, 457), (222.8, 445), (222.4, 434),                         # inner calf -> knee
    (220.8, 423), (218.2, 410), (215.6, 396), (213.2, 381), (211.2, 365),           # VMO -> inner thigh
    (209.4, 349), (207.8, 334), (206.4, 321), (205, 311.4), (202.8, 304.4),         # straight inner thigh
    (200, 302.4),                                                                   # crotch (round, thighs apart)
]
ARM_SPLAY = 0.05        # extra x per unit of y below the armpit (arm and hand only)

# Extend the forearm along its original axis, keeping the elbow and the hand's
# shape. The wrist moves from y=273 to 297; fingertips now reach mid-thigh.
FOREARM_EXTENSION = (13.4, 24.0)
_OUTER_FOREARM = BODY_HALF_D.index((322, 233.4))
_HAND_START = BODY_HALF_D.index((339, 270))
_HAND_END = BODY_HALF_D.index((317.2, 273.4))
_INNER_ELBOW = BODY_HALF_D.index((281.6, 225))
for _i in range(_OUTER_FOREARM, _INNER_ELBOW):
    _p = BODY_HALF_D[_i]
    _t = 1.0 if _HAND_START <= _i <= _HAND_END else min(1.0, max(0.0, (_p[1] - 225) / 48.0))
    BODY_HALF_D[_i] = (_p[0] + FOREARM_EXTENSION[0] * _t,
                       _p[1] + FOREARM_EXTENSION[1] * _t) + tuple(_p[2:])


def _splay(p):
    return (p[0] + ARM_SPLAY * max(0.0, p[1] - 160.0),) + tuple(p[1:])


_A0 = BODY_HALF_D.index((289.8, 157))
_A1 = BODY_HALF_D.index((255.5, 169, 'c'))
BODY_HALF_D = BODY_HALF_D[:_A0 + 1] + [_splay(p) for p in BODY_HALF_D[_A0 + 1:_A1]] + BODY_HALF_D[_A1:]
BODY_HALF = [B(*p) for p in BODY_HALF_D]


def body_outline():
    right = BODY_HALF
    left = [mirror_x(p) for p in reversed(right[1:-1])]
    return right + left


# Very quiet anatomy lines, open splines in design units (stroked only).
_BODY_DETAILS_D = [
    [(203, 157), (214, 164.5), (229, 165.5), (241.5, 159), (249.5, 149)],        # pectoral
    [(258.8, 165), (263.2, 151.5), (267.4, 138.5)],                                  # deltoid front border
    [(246, 265), (235, 281.5), (221, 295), (209, 301)],                            # inguinal line
    [(231, 427), (236.8, 431.6), (243.6, 431), (247.4, 426.4)],                  # kneecap
]


def body_details():
    lines = []
    for line in _BODY_DETAILS_D:
        pts = [B(*p) for p in line]
        lines.append(pts)
        lines.append([mirror_x(p) for p in pts])
    return lines


# Joint centres in body design units (screen-right = character's left side).
_BODY_JOINTS_D = {
    "Head": (200, 60), "Neck": (200, 92),
    "Spine3": (200, 128), "Spine2": (200, 163), "Spine1": (200, 198),
    "Spine": (200, 233), "Hips": (200, 268),
}
_SIDE_JOINTS_D = {
    "Shoulder": (221, 111), "Arm": (266.5, 136), "ForeArm": _splay((299.6, 225)),
    "Hand": _splay((326.4 + FOREARM_EXTENSION[0], 273 + FOREARM_EXTENSION[1])),
    "UpLeg": (228, 292), "Leg": (239, 436), "Foot": (243.8, 543), "ToeBase": (258, 579.5),
}
BODY_JOINTS = {k: B(*v) for k, v in _BODY_JOINTS_D.items()}
for _side, _s in (("Left", 1), ("Right", -1)):
    for _part, _p in _SIDE_JOINTS_D.items():
        _x, _y = B(*_p)
        BODY_JOINTS[_side + _part] = (CX + _s * (_x - CX), _y)

BODY_BONES = [("Hips", "Spine"), ("Spine", "Spine1"), ("Spine1", "Spine2"), ("Spine2", "Spine3"),
              ("Spine3", "Neck"), ("Neck", "Head")]
for _side in ("Left", "Right"):
    BODY_BONES += [("Spine3", _side + "Shoulder"), (_side + "Shoulder", _side + "Arm"),
                   (_side + "Arm", _side + "ForeArm"), (_side + "ForeArm", _side + "Hand"),
                   ("Hips", _side + "UpLeg"), (_side + "UpLeg", _side + "Leg"),
                   (_side + "Leg", _side + "Foot"), (_side + "Foot", _side + "ToeBase")]

REQUIRED = {"Hips", "Spine", "Head", "LeftArm", "LeftForeArm", "LeftHand", "RightArm", "RightForeArm",
            "RightHand", "LeftUpLeg", "LeftLeg", "LeftFoot", "RightUpLeg", "RightLeg", "RightFoot"}

# ---- body labels: two columns joined to the joints by leader lines (HumanIK style)

TEXT = {"Head": "Head", "Neck": "Neck", "Spine3": "Spine 3", "Spine2": "Spine 2", "Spine1": "Spine 1",
        "Spine": "Spine", "Hips": "Hips", "Shoulder": "Shoulder", "Arm": "Arm", "ForeArm": "Forearm",
        "Hand": "Hand", "UpLeg": "Up Leg", "Leg": "Leg", "Foot": "Foot", "ToeBase": "Toe"}

# Column geometry. Screen-right column (character's left side and the centre
# chain): text left-aligned at COL_TEXT_R; the leader runs from the joint centre
# to the bend (COL_BEND_R, label y) and then flat into the text.
COL_TEXT_R, COL_BEND_R, COL_GAP = 734.0, 704.0, 6.0
COL_TEXT_L, COL_BEND_L = 2 * CX - COL_TEXT_R, 2 * CX - COL_BEND_R

# Label rows (label centre y), set by hand and checked by check_body_labels():
# leaders as flat as possible, never crossing, clear of other joints.
_ROWS_R = {"Head": 52, "Neck": 70, "Shoulder": 88, "Spine3": 106, "Arm": 146, "Spine2": 175,
           "Spine1": 207, "ForeArm": 237, "Spine": 268, "Hips": 299, "Hand": 330, "UpLeg": 361,
           "Leg": 463, "Foot": 582, "ToeBase": 614}
BODY_LABEL_ROWS = {}
for _k, _v in _ROWS_R.items():
    if _k in ("Head", "Neck", "Spine3", "Spine2", "Spine1", "Spine", "Hips"):
        BODY_LABEL_ROWS[_k] = _v
    else:
        BODY_LABEL_ROWS["Left" + _k] = _v
        BODY_LABEL_ROWS["Right" + _k] = _v


def body_label_side(role):
    return "L" if role.startswith("Right") else "R"


def body_leader(role, ly):
    jx, jy = BODY_JOINTS[role]
    if body_label_side(role) == "R":
        return [(COL_TEXT_R - COL_GAP, ly), (COL_BEND_R, ly), (jx, jy)]
    return [(COL_TEXT_L + COL_GAP, ly), (COL_BEND_L, ly), (jx, jy)]


def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(ax + dx * t - p[0], ay + dy * t - p[1])


def _cross(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return (o1 * o2 < 0) and (o3 * o4 < 0)


def _angle_between(a, b, c, d):
    u = (b[0] - a[0], b[1] - a[1])
    v = (d[0] - c[0], d[1] - c[1])
    cs = abs(u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v))
    return math.degrees(math.acos(min(1.0, cs)))


# Clearance (viewBox units) a leader keeps from other joints, and the label row
# spacing. Required labels stay 31 apart so they all still fit at the minimum
# map size (scale ~0.52), where the optional ones in between hide.
CLEAR_REQ, CLEAR_OPT = 17.0, 13.0
ROW_ANY, ROW_REQ = 17.5, 31.0
MIN_CROSS_ANGLE = 30.0


def _leader_clear(role, ly):
    """The leader keeps clear of every other joint and crosses bones steeply."""
    pts = body_leader(role, ly)
    seg = (pts[1], pts[2])
    for other, p in BODY_JOINTS.items():
        if other == role:
            continue
        c = CLEAR_REQ if other in REQUIRED else CLEAR_OPT
        if _seg_dist(p, *seg) < c:
            return False
    for a, b in BODY_BONES:
        if role in (a, b):
            continue
        pa, pb = BODY_JOINTS[a], BODY_JOINTS[b]
        if _cross(seg[0], seg[1], pa, pb) and _angle_between(seg[0], seg[1], pa, pb) < MIN_CROSS_ANGLE:
            return False
    return True


def _pair_ok(role, ly, other, oly):
    if body_label_side(other) != body_label_side(role):
        return True
    need = ROW_REQ if (role in REQUIRED and other in REQUIRED) else ROW_ANY
    if abs(oly - ly) < need:
        return False
    p, q = body_leader(role, ly), body_leader(other, oly)
    return not _cross(p[1], p[2], q[1], q[2])


def check_body_labels(rows=None):
    rows = rows or BODY_LABEL_ROWS
    bad = []
    for role, ly in rows.items():
        if not _leader_clear(role, ly):
            bad.append((role, "joint/bone"))
        for other, oly in rows.items():
            if other < role and not _pair_ok(role, ly, other, oly):
                bad.append((role, other))
    return bad


def solve_body_labels(span=80, step=1.0, budget=400000):
    """Pick a row per label: leaders as flat as possible, no crossings, clear of joints.

    Depth-first in joint height order, cheapest rows first, with a node budget;
    the best complete layout found wins.
    """
    rows = {}
    for side in ("R", "L"):
        order = sorted((r for r in BODY_JOINTS if body_label_side(r) == side), key=lambda r: BODY_JOINTS[r][1])
        valid = {}
        for role in order:
            jy = BODY_JOINTS[role][1]
            c = [round(jy) + k * step for k in range(-int(span / step), int(span / step) + 1)]
            valid[role] = sorted((y for y in c if 44 <= y <= 624 and _leader_clear(role, y)),
                                 key=lambda y: abs(y - jy))
        best = [None, 1e18]
        nodes = [0]

        def dfs(i, placed, cost):
            nodes[0] += 1
            if nodes[0] > budget or cost >= best[1]:
                return
            if i == len(order):
                best[0], best[1] = dict(placed), cost
                return
            role = order[i]
            jy = BODY_JOINTS[role][1]
            for ly in valid[role]:
                c = cost + (ly - jy) ** 2
                if c >= best[1]:
                    break
                if all(_pair_ok(role, ly, o, oly) for o, oly in placed.items()):
                    placed[role] = ly
                    dfs(i + 1, placed, c)
                    del placed[role]

        dfs(0, {}, 0.0)
        if best[0] is None:
            raise RuntimeError("no leader layout for side " + side)
        rows.update(best[0])
    return rows


def body_labels():
    rows = BODY_LABEL_ROWS or solve_body_labels()
    out = {}
    for role in BODY_JOINTS:
        base = role[4:] if role.startswith("Left") else role[5:] if role.startswith("Right") else role
        ly = rows[role]
        if body_label_side(role) == "R":
            out[role] = (COL_TEXT_R, ly, "left", TEXT[base], body_leader(role, ly))
        else:
            out[role] = (COL_TEXT_L, ly, "right", TEXT[base], body_leader(role, ly))
    return out


BODY_HEADINGS = [("RIGHT", COL_TEXT_L, 18, "right"), ("LEFT", COL_TEXT_R, 18, "left")]


# --------------------------------------------------------------------------- hands

# Hand drawing board: the LEFT hand, palm towards the viewer, fingers up, thumb
# pointing to screen-left (the centre of the panel). The right hand is its mirror.
HK = 1.16
HOX, HOY = 513.0, 22.0


def Hd(x, y, *rest):
    return (HOX + x * HK, HOY + y * HK) + tuple(rest)


def _v(a, b):
    return (b[0] - a[0], b[1] - a[1])


def _unit(v):
    l = math.hypot(*v)
    return (v[0] / l, v[1] / l)


# finger: knuckle (MCP, joint 1) and fingertip in design units; half widths at
# the web, PIP, DIP and the tip radius. Joint 2 / 3 sit at 44 % / 72 % of the
# knuckle-to-tip length.
FINGERS_D = {
    "Index":  dict(mcp=(166, 222), tip=(156, 51), w=(18.4, 17.0, 16.0, 15.0)),
    "Middle": dict(mcp=(219, 214), tip=(237, 37), w=(19.0, 17.6, 16.6, 15.4)),
    "Ring":   dict(mcp=(266, 228), tip=(296, 71), w=(18.0, 16.6, 15.6, 14.4)),
    "Pinky":  dict(mcp=(299, 254), tip=(354, 138), w=(16.0, 14.8, 13.8, 12.8)),
}
PIP_AT, DIP_AT = 0.44, 0.72
WEB_T = {"Index": 0.25, "Middle": 0.23, "Ring": 0.23, "Pinky": 0.22}   # web height, fraction of length


def _finger_frame(f):
    u = _unit(_v(f["mcp"], f["tip"]))
    n = (-u[1], u[0])            # n points to the pinky side for this hand (fingers up)
    return u, n


def _finger_len(f):
    return math.hypot(*_v(f["mcp"], f["tip"]))


def finger_joints_d(f):
    u, _ = _finger_frame(f)
    L = _finger_len(f)
    m = f["mcp"]
    return [m, (m[0] + u[0] * L * PIP_AT, m[1] + u[1] * L * PIP_AT),
            (m[0] + u[0] * L * DIP_AT, m[1] + u[1] * L * DIP_AT)]


def _finger_side(name, side):
    """Points up one side of a finger (side=-1 thumb side, +1 pinky side), from the web."""
    f = FINGERS_D[name]
    u, n = _finger_frame(f)
    L = _finger_len(f)
    m = f["mcp"]
    w1, w2, w3, wt = f["w"]
    prof = [(L * WEB_T[name], w1 + 1.2), (L * 0.33, w1 - 0.4), (L * PIP_AT, w2 + 0.5), (L * 0.58, w2 - 0.6),
            (L * DIP_AT, w3 + 0.4), (L * 0.84, w3 - 0.3), (L - wt * 0.95, wt)]
    return [(m[0] + u[0] * t + n[0] * w * side, m[1] + u[1] * t + n[1] * w * side) for t, w in prof]


def _finger_tip(name):
    f = FINGERS_D[name]
    u, n = _finger_frame(f)
    L = _finger_len(f)
    wt = f["w"][3]
    c = (f["mcp"][0] + u[0] * (L - wt), f["mcp"][1] + u[1] * (L - wt))
    pts = []
    for deg in (-52, -24, 0, 24, 52):         # thumb side -> pinky side
        a = math.radians(deg)
        d = (u[0] * math.cos(a) + n[0] * math.sin(a), u[1] * math.cos(a) + n[1] * math.sin(a))
        pts.append((c[0] + d[0] * wt, c[1] + d[1] * wt))
    return pts


# Thumb axis: CMC (joint 1), MCP (2), IP (3) and the tip centre, in design units.
THUMB_D = dict(cmc=(178, 330), mcp=(126, 283), ip=(82, 245), tipc=(37, 226))


def _thumb_frame(a, b):
    u = _unit(_v(a, b))                  # towards the tip
    up = (-u[1], u[0])                   # towards the index (upper edge)
    return u, up


def thumb_joints_d():
    return [THUMB_D["cmc"], THUMB_D["mcp"], THUMB_D["ip"]]


def _thumb_station(seg_a, seg_b, frac, w):
    """Point at `frac` along the thumb segment a->b, offset `w` towards the index (w<0: palm side)."""
    u, up = _thumb_frame(seg_a, seg_b)
    p = (seg_a[0] + (seg_b[0] - seg_a[0]) * frac, seg_a[1] + (seg_b[1] - seg_a[1]) * frac)
    return (p[0] + up[0] * w, p[1] + up[1] * w)


# Finger webs (bottom of the gap between two fingers), in hand design units.
WEBS_D = {("Index", "Middle"): (191.5, 187.5), ("Middle", "Ring"): (245.5, 194.5), ("Ring", "Pinky"): (293.5, 221)}


def _web(left, right):
    b = WEBS_D[(left, right)]
    ul, _ = _finger_frame(FINGERS_D[left])
    ur, _ = _finger_frame(FINGERS_D[right])
    u = _unit((ul[0] + ur[0], ul[1] + ur[1]))
    n = (-u[1], u[0])
    return [(b[0] + u[0] * 5.5 - n[0] * 4.6, b[1] + u[1] * 5.5 - n[1] * 4.6), b,
            (b[0] + u[0] * 5.5 + n[0] * 4.6, b[1] + u[1] * 5.5 + n[1] * 4.6)]


def hand_outline_left_d():
    t = THUMB_D
    tc = t["tipc"]
    pts = []
    # forearm (radial side) up to the wrist, then the thenar eminence and the thumb's palm edge
    pts += [(190, 560), (186, 520), (181.5, 478), (177.5, 436), (175, 402), (171.4, 382)]
    pts += [(161.4, 366.6), (145.6, 350), (129.4, 332.4), (113.6, 314.6), (99.4, 298), (85, 282.8),
            (70.6, 269.4), (55.6, 257.4), (41.4, 248.4)]
    r = 16.8
    u2, up2 = _thumb_frame(t["ip"], tc)
    for deg in (-62, -30, 0, 30, 62):            # round tip, palm side -> index side
        ang = math.radians(deg)
        d = (u2[0] * math.cos(ang) + up2[0] * math.sin(ang), u2[1] * math.cos(ang) + up2[1] * math.sin(ang))
        pts.append((tc[0] + d[0] * r, tc[1] + d[1] * r))
    # thumb, upper edge back to the thumb-index web and the radial side of the index
    pts += [(52, 210.6), (68.4, 216), (84, 224.4), (98.6, 234.4), (111.8, 245.4)]
    pts += [(121.8, 255.6), (128.6, 259.4), (135.6, 256.6), (141.4, 247.4), (144.4, 234)]
    order = ["Index", "Middle", "Ring", "Pinky"]
    for i, name in enumerate(order):
        if i > 0:
            pts += _web(order[i - 1], name)
        pts += _finger_side(name, -1)[1:] + _finger_tip(name)
        pts += list(reversed(_finger_side(name, +1)))[:-1]
    # ulnar edge (hypothenar) down to the wrist and the forearm
    pts += [(327, 237.5), (321.6, 253), (315.6, 272), (308.2, 293), (300.6, 312.6), (293, 331.4),
            (286.6, 347.6), (282.6, 361), (281.8, 376), (283, 398), (287, 432), (293, 468), (301, 503),
            (310, 538), (318, 564)]
    return pts


def hand_outline_left():
    return [Hd(*p) for p in hand_outline_left_d()]


HAND_JOINTS = {}
HAND_BONES = []
_WRIST_D = (225, 371)
for _side, _s in (("Left", 1), ("Right", -1)):
    _m = lambda p, s=_s: (CX + s * (p[0] - CX), p[1])
    _wrist = _side + "Hand"
    HAND_JOINTS[_wrist] = _m(Hd(*_WRIST_D))
    for _name, _f in FINGERS_D.items():
        for _i, _p in enumerate(finger_joints_d(_f), 1):
            HAND_JOINTS["%sHand%s%d" % (_side, _name, _i)] = _m(Hd(*_p))
    for _i, _p in enumerate(thumb_joints_d(), 1):
        HAND_JOINTS["%sHandThumb%d" % (_side, _i)] = _m(Hd(*_p))
    for _name in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        _r = "%sHand%s" % (_side, _name)
        HAND_BONES += [(_wrist, _r + "1"), (_r + "1", _r + "2"), (_r + "2", _r + "3")]


def _finger_label_pos(name):
    if name == "Thumb":
        x, y = Hd(*THUMB_D["tipc"])
        return (x + 2, y - 40)
    f = FINGERS_D[name]
    u, _ = _finger_frame(f)
    x, y = Hd(*f["tip"])
    return (x + u[0] * 22, y + u[1] * 22)


HAND_LABELS = {}
for _side, _s in (("Left", 1), ("Right", -1)):
    for _name in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        x, y = _finger_label_pos(_name)
        HAND_LABELS["%sHand%s" % (_side, _name)] = (CX + _s * (x - CX), y, "center", _name)
    wx, wy = Hd(*_WRIST_D)
    HAND_LABELS[_side + "Hand"] = (CX + _s * (wx - CX), wy + 36, "center", "Wrist")
HAND_HEADINGS = [("RIGHT HAND", 14, 20, "left"), ("LEFT HAND", 986, 20, "right")]
