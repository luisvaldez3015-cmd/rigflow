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
# Leader lines (Body map): drawn in the label's current colour.
LEADER = {"widthPx": 1.0, "opacity": 0.38, "hotOpacity": 0.9}
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
        "leader": LEADER,
    }


JOINT_STYLE_DOC = r'''# Character definition: joint and bone style

Art for the Match step's Body and Hands maps. `body.svg` and `hands.svg` are flat
silhouettes only; the app paints bones, joints and labels on top from
`layout.json`. Every hex value and pixel size below is also in `layout.json`
under `style`, so code can read them instead of copying them.

## Coordinates

- Both SVGs and all `layout.json` positions use the viewBox `0 0 1000 640`.
- Map to the widget with `scale = min(w / 1000, h / 640)`, centred:
  `ox = (w - 1000 * scale) / 2`, `oy = (h - 640 * scale) / 2`.
- Render the SVG with `QSvgRenderer.render(painter, QRectF(ox, oy, 1000 * scale, 640 * scale))`.
  The hand forearms run a few units past the bottom edge but fade to fully
  transparent at y=640, so no clipping is needed.
- Character orientation: the figure faces the viewer, so the character's
  RIGHT side is on the screen LEFT. Hands are drawn palm towards the viewer,
  fingers up, thumbs pointing to the centre; the right hand is the exact mirror
  of the left.

## Paint order

1. Silhouette SVG.
2. Leader lines (Body map only, see Labels). They run to the joint centre and are
   covered by the bones and spheres painted after them.
3. All bones (parent to child, list order of `bones`).
4. All joints; draw the waiting joint last so its glow sits on top.
5. Labels, then headings.

## Joint radius

`layout.json` gives `r` in viewBox units per joint (body: required 10,
optional 7; hands: wrist 12, fingers 8.5). On screen:

```
r_px = max(min_px, r * scale)
```

with `min_px` = 6 (required) / 4.5 (optional) for the body and 6.5 / 5 for the
hands (`style.jointMinRadiusPx`). Hit-test radius: `max(r_px + 4, 10)` px.

Spacing: no two joint centres are closer than 3.4 x the larger radius in the
body (Head to Neck, then Spine to Hips) and 4.9 x in the hands (Pinky 2 to 3).

## Joint (the sphere)

All sizes in px, after `r_px` is resolved. Colours per state:

| State | When | Highlight | Base | Shadow | Ring | Ring width |
|---|---|---|---|---|---|---|
| `assigned` | joint chosen in Maya | `#a6e3ae` | `#58b368` | `#3b7f48` | `#2a5a33` | 1.2 |
| `waiting` | slot clicked, waiting for a Maya selection | `#8fe3f6` | `#23b7db` | `#16809c` | `#0f5d72` | 1.2 |
| `review` | assigned but needs a look | `#f6df9c` | `#e0b84c` | `#a88430` | `#6e5520` | 1.2 |
| `invalid` | assigned joint that failed validation | `#f0a09d` | `#d9534f` | `#9c3431` | `#5e1f1d` | 1.2 |
| `required` | required role still empty | `#4a4446` | `#332f30` | `#262425` | `#d9534f` | 1.8 |
| `empty` | optional role still empty | `#7a868c` | `#4f5a60` | `#3a4247` | `#8d999f` | 1.0 |

Layers, bottom to top:

1. **Contact shadow**: circle at `(x, y + 0.8)`, radius `r + 1.6`, `#16191b` at 55 % opacity, no pen.
   It lifts the sphere off the bone and the silhouette.
2. **Sphere**: circle radius `r`, brush `QRadialGradient(centre=(x, y), radius=r, focal=(x - 0.38r, y - 0.42r))`
   with stops 0 = highlight, 0.55 = base, 1 = shadow; pen = ring colour at ring width.
3. **Wire equator** (the Maya joint look): ellipse `rx = 0.9r`, `ry = 0.3r`, white at 16 %, 0.9 px, no brush.
   Skip it when `r < 5.5` and for the `required` state.
4. **Required marker**: `required` only, a filled dot of radius `0.28r` in `#d9534f` at 90 %.
5. **Hand numbers**: finger joints on the Hands map show their index (1, 2, 3) when `r >= 7.5`.
   Segoe UI DemiBold, pixel size `max(8, int(1.05r))`, centred. Text `#14251a` at 85 % on
   assigned, waiting, review and invalid; `#dfe5e8` at 80 % on empty and required.

Interaction states, added on top of the colour state:

- **Waiting glow**: before the sphere, a radial gradient disc of radius `r + 9` from cyan
  `#23b7db` at 55 % (at the sphere edge) to 0 %; plus an open ring at `r + 4`, `#4cc8e6`
  at 95 %, 1.3 px. A gentle pulse (ring opacity 95 % to 45 %, 1.2 s) is welcome but optional.
- **Hovered**: draw the sphere at `1.12 r` and add an open ring at `r + 3.2`, white at 85 %, 1.3 px.

## Bone (Maya's tapered pyramid)

A bone is a kite from the parent joint centre to just short of the child joint:

```
d   = |child - parent|,  u = (child - parent) / d,  n = (-u.y, u.x)
a   = min(1.25 * r_parent, 0.3 * d)        # widest point, just outside the parent sphere
hw  = 0.62 * r_parent                      # half width at the widest point
W1  = parent + u * a + n * hw
W2  = parent + u * a - n * hw
tip = child - u * (r_child + 1.5)          # 1.5 px gap before the child sphere
```

- Fill two facets: triangle `(parent, W1, tip)` and triangle `(parent, tip, W2)`.
  The facet on the side of `n` that faces the upper-left light
  (`n.x * -0.6 + n.y * -0.8 > 0`) takes the lit colour, the other takes the shaded colour.
  This split reads as the pyramid's ridge, like Maya's bone display.
- Outline the kite `(parent, W1, tip, W2)` with `#262b2e` at 90 %, 0.9 px, round joins.
- The parent end is hidden under the parent sphere, so the visible bone starts wide at the
  sphere and narrows towards the child: direction is readable at a glance.

Bone colour:

| Parent and child | Lit | Shaded |
|---|---|---|
| both `assigned` | `#6cc27a` | `#4a9a58` |
| both resolved (`assigned` or `review`), at least one `review` | `#e6c464` | `#b8933a` |
| anything else (an end is empty, required, waiting or invalid) | `#5f6a70` | `#4a5459` |

So a chain turns green bone by bone as the artist assigns it; the waiting joint keeps its
incoming bone neutral and gets the attention from its glow instead.

## Labels

- Font: Segoe UI. Required roles 11 px regular `#e6e6e6`; optional roles 10 px regular `#a0a0a0`.
  Tint a label `#e88a87` while its joint is `required` (empty) and `#6fd3ec` while it is `waiting`.
  Hand finger names and "Wrist" always use the 11 px required style.
- Pixel sizes are fixed: labels do not scale with the figure.
- Anchor: `x, y` in viewBox units; `y` is the vertical centre of the text line, `align` is
  `left`, `right` or `center` around `x`. Lay out in a rect of the font's full height centred on `y`.
- `minScale`: hide the label (and its leader) while `scale < minScale`; the joint tooltip still
  names it. Measured with a collision check (glyph box + 2.5 px against the silhouette edge,
  every bone, every joint, every leader and every other label) from scale 0.45 to 1.40, so a
  visible label never touches anything. At 1110 x 600 every label shows; at 910 x 330
  (scale 0.52) every required label still shows and only the optional Neck and the
  character's left Shoulder hide.
- `compact` (optional, not used by this art): when present and `scale < compact.below`, use
  `compact.x/y/align` instead.

### Body map: label columns and leader lines

The A-pose figure is narrow, so the Body labels sit in two columns beside it, HumanIK style,
and every label has a `leader`: a polyline in viewBox units `[[x, y], ...]` from the end next to
the text to the joint centre.

- Screen-left column (the character's RIGHT side): text right-aligned at x=266.
  Screen-right column (the character's LEFT side and the centre chain Head, Neck, Spine 3..1,
  Spine, Hips): text left-aligned at x=734. Headings "RIGHT"/"LEFT" sit on top of the columns.
- Each leader is `[text end, bend, joint centre]`: a short flat run from 6 units off the text
  to the bend at x=296 / x=704, then straight to the joint. Rows were chosen so that leaders never
  cross each other, stay at least 17 units from every other required joint (13 from optional
  ones) and cross bones at 30 degrees or more. Required labels are at least 31 units apart, so
  they still fit at the minimum map size.
- Draw: `QPen(label colour, 1.0 px)` with round caps and joins, alpha 38 %; 90 % while the joint
  is `waiting` or hovered (`style.leader`: `widthPx`, `opacity`, `hotOpacity`). Use the label's
  current colour, so a required-empty leader is muted red and the waiting one is cyan. Paint the
  leaders before the bones (see Paint order): the line ends under the sphere, so there is no
  gap to compute and the hover/waiting rings stay clean.
- Skip a leader whenever its label is hidden by `minScale`.
- Hands labels have no leader: `{Side}Hand{Finger}` sits above the fingertip on the finger's
  axis (Thumb above the thumb tip) and `{Side}Hand` ("Wrist") inside the forearm under the
  wrist joint.
- Headings ("RIGHT"/"LEFT", "RIGHT HAND"/"LEFT HAND"): 10 px, weight 600, letter spacing
  1.6 px, `#8a8a8a`, always shown.

## Silhouette art

- Fill: vertical gradient `#3c4347` to `#33393c`; rim `#5c686e` 1.6 units; under it a 6-unit
  halo stroke `#1d2123` at 55 % that separates the figure from the `#2f2f2f` card.
- Body: athletic male figure in A-pose (arms about 25 degrees out, palms forward, fingers and
  thumb visible), about 8 heads (crown y=12, soles y=631), with a soft ground shadow and a few
  quiet anatomy lines (pectorals, front deltoid border, inguinal lines, kneecaps) in `#465055`.
- Joints sit on the anatomy of that pose: Arm in the shoulder joint under the deltoid, ForeArm
  at the elbow, Hand at the wrist, UpLeg at the hip socket, Leg at the knee, Foot at the ankle,
  ToeBase at the ball of the foot, Hips to Spine 3 evenly up the torso, Neck at the base of the
  neck, Head at the base of the skull, Shoulder at the sternal end of the clavicle.
- Hands: open hands, palms towards the viewer, fingers spread with natural lengths (middle
  longest, pinky shortest), thumb set low on a full thenar and angled to the centre; joint 1 of
  each finger is the knuckle inside the palm, 2 and 3 the finger joints; the thumb's 1 is the
  CMC joint at the base of the thenar. The forearm stubs fade out at the bottom edge so the
  hands float without a hard cut.
- No text and no joints inside the SVGs.
'''
