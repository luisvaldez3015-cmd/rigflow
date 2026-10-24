# Character definition: joint and bone style

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
2. All bones (parent to child, list order of `bones`).
3. All joints; draw the waiting joint last so its glow sits on top.
4. Labels, then headings.

## Joint radius

`layout.json` gives `r` in viewBox units per joint (body: required 10,
optional 7; hands: wrist 12, fingers 8.5). On screen:

```
r_px = max(min_px, r * scale)
```

with `min_px` = 6 (required) / 4.5 (optional) for the body and 6.5 / 5 for the
hands (`style.jointMinRadiusPx`). Hit-test radius: `max(r_px + 4, 10)` px.

Spacing: no two joint centres are closer than 3.7 x the larger radius in the
body (Spine to Hips, Foot to Toe are the tightest) and 6 x in the hands.

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
- `minScale`: hide the label while `scale < minScale` (the joint tooltip still names it).
  These were measured with a collision check (glyph box + 2.5 px against the silhouette edge,
  every bone, every joint and every other label) from scale 0.45 to 1.40, so a visible label never
  touches anything. At the 1110 x 600 map every label shows; at 910 x 330 the optional
  Neck, Shoulder and Spine 1-3 labels hide.
- `compact`: when present and `scale < compact.below`, use `compact.x/y/align` instead.
  Only Spine and Hips have one: below 0.7 the torso is too narrow for 11 px text, so their
  labels move just outside the waist on the screen-right side.
- Hands labels are keyed `{Side}Hand{Finger}` (finger name above the fingertip) and
  `{Side}Hand` ("Wrist", inside the forearm under the wrist joint).
- Headings ("RIGHT"/"LEFT", "RIGHT HAND"/"LEFT HAND"): 10 px, weight 600, letter spacing
  1.6 px, `#8a8a8a`, always shown.

## Silhouette art

- Fill: vertical gradient `#3c4347` to `#33393c`; rim `#5c686e` 1.6 units; under it a 6-unit
  halo stroke `#1d2123` at 55 % that separates the figure from the `#2f2f2f` card.
- Body: neutral athletic mannequin in T-pose, about 7.6 heads (crown y=16, floor y=630),
  with a soft ground shadow and a few quiet anatomy lines (pectorals, inguinal lines) in `#465055`.
- Hands: forearm stubs fade out at the bottom edge so the hands float without a hard cut.
- No text and no joints inside the SVGs.
