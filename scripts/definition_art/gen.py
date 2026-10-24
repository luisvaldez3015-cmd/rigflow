"""Write body.svg, hands.svg and layout.json into the folder given as argv[1]."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom  # noqa: E402
import style  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets", "definition")
os.makedirs(OUT, exist_ok=True)

FILL_TOP, FILL_BOTTOM = "#3c4347", "#33393c"
RIM = "#5c686e"
HALO = "#1d2123"
DETAIL = "#465055"


def polyline_d(pts):
    return "M" + " L".join("%.1f,%.1f" % p for p in pts)


def svg_doc(body, defs):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!-- RigFlow character definition art. Flat silhouette only: joints, bones and\n'
            '     labels are painted by the app from layout.json in these viewBox units. -->\n'
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.2" baseProfile="tiny" '
            'width="1000" height="640" viewBox="0 0 1000 640">\n'
            '<defs>\n' + defs + '</defs>\n' + body + '</svg>\n')


def gradient(gid, y1, y2, stops):
    s = "".join('<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % st for st in stops)
    return ('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="0" y1="%s" x2="0" y2="%s">%s'
            '</linearGradient>\n' % (gid, y1, y2, s))


def silhouette(pid, d, fill, stroke, halo):
    return ('<path d="%s" fill="none" stroke="%s" stroke-opacity="0.55" stroke-width="6" '
            'stroke-linejoin="round"/>\n'
            '<path id="%s" d="%s" fill="%s" stroke="%s" stroke-width="1.6" stroke-linejoin="round"/>\n'
            % (d, halo, pid, d, fill, stroke))


def write_body():
    defs = gradient("skin", 12, 632, [(0, FILL_TOP, 1), (1, FILL_BOTTOM, 1)])
    body = '<ellipse cx="500" cy="631" rx="92" ry="5" fill="#25292b" fill-opacity="0.7"/>\n'
    body += silhouette("body", geom.catmull_path(geom.body_outline()), "url(#skin)", RIM, HALO)
    body += '<g fill="none" stroke="%s" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">\n' % DETAIL
    for line in geom.body_details():
        d = geom.catmull_path(line, closed=False) if len(line) > 2 else polyline_d(line)
        body += '<path d="%s"/>\n' % d
    body += '</g>\n'
    with open(os.path.join(OUT, "body.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(svg_doc(body, defs))


def write_hands():
    # The forearm stubs fade out towards the bottom edge.
    defs = gradient("skin", 40, 640, [(0, FILL_TOP, 1), (0.86, FILL_BOTTOM, 1), (1, FILL_BOTTOM, 0)])
    defs += gradient("rim", 40, 640, [(0, RIM, 1), (0.84, RIM, 1), (0.99, RIM, 0)])
    defs += gradient("halo", 40, 640, [(0, HALO, 1), (0.84, HALO, 1), (0.99, HALO, 0)])
    left = geom.hand_outline_left()
    right = [geom.mirror_x(p) for p in left]
    body = ""
    for name, pts in (("right-hand", right), ("left-hand", left)):
        body += silhouette(name, geom.catmull_path(pts), "url(#skin)", "url(#rim)", "url(#halo)")
    with open(os.path.join(OUT, "hands.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(svg_doc(body, defs))


def joints_dict(joints, required_r, optional_r, required):
    return {role: {"x": round(x, 1), "y": round(y, 1),
                   "r": required_r if role in required else optional_r,
                   "required": role in required}
            for role, (x, y) in joints.items()}


def labels_dict(labels, min_scales, compact=None):
    out = {}
    for role, item in labels.items():
        x, y, a, t = item[:4]
        out[role] = {"text": t, "x": round(x, 1), "y": round(y, 1), "align": a,
                     "minScale": min_scales.get(role, 0)}
        if len(item) > 4:
            out[role]["leader"] = [[round(px, 1), round(py, 1)] for px, py in item[4]]
        if compact and role in compact:
            cx, cy, ca = compact[role]
            out[role]["compact"] = {"x": cx, "y": cy, "align": ca, "below": 0.7}
    return out


def write_layout(min_scales=None):
    min_scales = min_scales or {}
    layout = {
        "viewBox": [0, 0, geom.W, geom.H],
        "style": style.as_json(),
        "body": {
            "svg": "body.svg",
            "joints": joints_dict(geom.BODY_JOINTS, 10, 7, geom.REQUIRED),
            "bones": [list(b) for b in geom.BODY_BONES],
            "labels": labels_dict(geom.body_labels(), min_scales.get("body", {})),
            "headings": [{"text": t, "x": x, "y": y, "align": a} for t, x, y, a in geom.BODY_HEADINGS],
        },
        "hands": {
            "svg": "hands.svg",
            "joints": joints_dict(geom.HAND_JOINTS, 12, 8.5, geom.REQUIRED),
            "bones": [list(b) for b in geom.HAND_BONES],
            "labels": labels_dict(geom.HAND_LABELS, min_scales.get("hands", {})),
            "headings": [{"text": t, "x": x, "y": y, "align": a} for t, x, y, a in geom.HAND_HEADINGS],
        },
    }
    with open(os.path.join(OUT, "layout.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(layout, f, indent=1)


if __name__ == "__main__":
    write_body()
    write_hands()
    ms = {}
    p = os.environ.get("RIGFLOW_MIN_SCALES", os.path.join(OUT, "_min_scales.json"))
    if os.path.exists(p):
        with open(p) as f:
            ms = json.load(f)
    write_layout(ms)
    with open(os.path.join(OUT, "joint-style.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(style.JOINT_STYLE_DOC)
    print("wrote", OUT)
