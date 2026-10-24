"""Joint/bone/label style shared by the mockup renderer and layout.json."""

JOINT = {
    #            highlight   base       shadow     ring       ring width (px)
    "assigned": ("#a6e3ae", "#58b368", "#3b7f48", "#2a5a33", 1.2),
    "review":   ("#f6df9c", "#e0b84c", "#a88430", "#6e5520", 1.2),
    "waiting":  ("#8fe3f6", "#23b7db", "#16809c", "#0f5d72", 1.2),
    "invalid":  ("#f0a09d", "#d9534f", "#9c3431", "#5e1f1d", 1.2),
    "required": ("#4a4446", "#332f30", "#262425", "#d9534f", 1.8),
    "empty":    ("#7a868c", "#4f5a60", "#3a4247", "#8d999f", 1.0),
}
BONE = {  # (lit facet, shaded facet)
    "neutral": ("#5f6a70", "#4a5459"),
    "assigned": ("#6cc27a", "#4a9a58"),
    "review": ("#e6c464", "#b8933a"),
}
BONE_EDGE = "#262b2e"
MIN_PX = {"body": (6.0, 4.5), "hands": (6.5, 5.0)}   # (required, optional) minimum radius in px
LABEL = {"family": "Segoe UI", "requiredPx": 11, "optionalPx": 10,
         "required": "#e6e6e6", "optional": "#a0a0a0", "requiredEmpty": "#e88a87", "waiting": "#6fd3ec",
         "headingPx": 10, "headingWeight": 600, "headingLetterSpacingPx": 1.6, "heading": "#8a8a8a"}


def as_json():
    return {
        "joint": {k: {"highlight": v[0], "base": v[1], "shadow": v[2], "ring": v[3], "ringWidthPx": v[4]}
                  for k, v in JOINT.items()},
        "jointMinRadiusPx": {k: {"required": v[0], "optional": v[1]} for k, v in MIN_PX.items()},
        "bone": {k: {"lit": v[0], "shaded": v[1]} for k, v in BONE.items()},
        "boneEdge": BONE_EDGE,
        "label": LABEL,
    }
