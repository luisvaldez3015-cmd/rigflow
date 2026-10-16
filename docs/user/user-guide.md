# RigFlow User Guide

RigFlow transfers body animation from one skeleton to another inside Maya,
even when the two characters have different proportions, joint names and
hierarchies. The interface is a three-step flow:

**1 Setup → 2 Match → 3 Transfer**

The step indicator in the top-right corner always shows where you are.

## Open RigFlow

Click the **RigFlow** shelf button (see the Installation Guide) or run:

```python
import rigflow
rigflow.launch()
```

The window docks like any Maya panel. **Help → Create demo scene** builds two
sample characters so you can try the whole flow without any files.

## Step 1 · Setup

Three slot cards sit at the top:

| Card | What it needs | How to fill it |
|------|---------------|----------------|
| **Mesh** (optional) | The destination character's geometry | Select the mesh in Maya and press **Use selection**, or **Browse…** / drop an `.fbx` `.ma` `.mb` file |
| **Rig** (required) | The skeleton that will receive the animation | Select its root joint (or a skinned mesh) and press **Use selection**, or **Browse…** |
| **Anim** | The source animation | **Add file…** (Mixamo exports, game skeletons, MotionBuilder files) or **From scene…** to pick an animated skeleton already in the scene |

Each card shows a status dot and what RigFlow detected: mesh and vertex
counts, root joint, joint count, naming convention, how many of the 15
required roles were found, frame range of the clip.

The big **+** tile in the middle is the fastest way to add an animation:
click it (or drop a file on it) and choose *From file…* or *From scene…*.
Once you have animations the area turns into the list; each row shows the
convention, frame range, status, and the actions **Match**, **Transfer**,
**Replace** and **Remove**. The small **+** under the list adds more clips;
each clip keeps its own mapping.

Press **Validate**. RigFlow matches the skeletons automatically and tells you
the result next to the button: green *Ready: n roles matched*, yellow *n to
review*, or a red error with a hint. **Next: Match ›** opens step 2.

## Step 2 · Match ("New animation")

Two viewports: **Mesh A** is the source character, **Mesh B** is your
destination. Both show their skeletons; Maya's own selection highlight marks
the joints you click.

- To correct a correspondence: click a joint in Mesh A, click the matching
  joint in Mesh B (the *Selection* readout shows A and B), press **Match**.
  The pair becomes a manual match and the counters update.
- **Unmatch** drops the pair of the selected joint (the role turns red if it
  is required, gray if it is optional).
- **Auto-match** recomputes everything automatically but keeps your manual
  corrections.
- **Details** expands the full table (status, role, A joint, B joint,
  confidence, manual, exclude) with the two joint hierarchies, **Save / Load
  preset…** and **Reset to automatic**.

The line under the viewports shows the validation result. **Next: Transfer ›**
is enabled as soon as there are no errors. See the Skeleton Matching Guide
for how the automatic matching decides.

## Step 3 · Transfer

The large viewport shows both characters with the live retarget connected:
the destination follows the source as you **Play**, **Pause**, **Stop** or
scrub the timeline. Nothing is written yet.

- **Bake to animation layer** (on by default) keeps your existing animation
  safe on the base layer.
- **Transfer** bakes the motion onto the destination joints and shows a
  result card: backend, layer name, joints baked, bone-length error, time.
- **New anim** takes you back to Setup to add the next animation; the
  transferred clip stays in the list with status *Transferred*.
- **Done** returns to Setup. **‹ Back** returns to Match to fix something.

The Animation Transfer Guide explains the backends, the baking options and
the checks RigFlow performs on every bake.

## After the transfer

The destination's facial joints and controls were never part of the body
mapping, so they are untouched: open your facial controls and keep keying.
The transferred body motion lives on the `rigflow_transfer` animation layer;
mute it to compare, lower its weight to blend, or delete it to start over.
Ctrl+Z right after a transfer removes it in one step.

## Tips

- Several animations for the same pair of characters: save a mapping preset
  from **Details** after the first one and load it for the next.
- **Help** gives you every guide, the repository, issue reporting and an
  *About* dialog whose environment details you can paste into bug reports.
