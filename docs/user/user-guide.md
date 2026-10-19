# RigFlow User Guide

RigFlow transfers body animation from one skeleton to another inside Maya,
even when the two characters have different proportions, joint names and
hierarchies. Add two models and RigFlow proposes the steps:

**1 Setup → 2 Match → 3 Transfer**

For a destination with geometry but no skeleton: **Setup → Rig → Match → Transfer**.

The step indicator in the top-right corner always shows where you are.

## Open RigFlow

Click the **RigFlow** shelf button (see the Installation Guide) or run:

```python
import rigflow
rigflow.launch()
```

The window docks like any Maya panel. **Help → Create demo scene** builds two
sample characters so you can try the whole flow without any files.

## Step 1 · Add your models

Click the big **+ · Add a model** tile and choose **From file…**, **Use Maya
selection**, or **From scene…**. You can also drop a `.ma`, `.mb`, `.fbx` or
`.obj` file on the empty area. A model can be a whole character, an animated
skeleton such as Mixamo, or geometry without a rig. Selecting a skinned mesh
also detects its skeleton.

RigFlow creates a **Model A** card with three small detection slots:

- **Mesh**: geometry and vertex count.
- **Rig**: detected skeleton and joint count.
- **Anim**: detected animation and frame count.

Each slot says **Detected** or **None**; hover it for details such as skinning,
root joint, naming convention, required roles or frame range. Slots fill
automatically when you add the model. **Replace…**, or dropping a file on a
card, replaces the entire model. **Remove** removes the model and its owned
import; models taken from the existing Maya scene remain in that scene.

Press the small **+ · Add the second model** below the first card to add
**Model B**. The two cards sit side by side. The banner below them explains
the proposed process and direction:

- Animated source and rigged destination: **Start: Match ›**.
- Rigged source and mesh-only destination: **Start: Rig ›**, followed by
  Match and Transfer when the source is animated.
- Both models animated: Model A is the default source. **Swap direction**
  makes Model B the source instead.
- No transferable content: the banner explains what is missing.

Starting the plan matches the joints automatically. The step indicator updates
to the proposed process.

## Rig · When the destination has no skeleton

RigFlow copies the source skeleton and fits it to the destination mesh. The
viewport isolates the mesh and fitted skeleton; the line below shows scale
and joint count. Move joints in Maya if needed, then press **Bind skin ›**.
This skins the mesh and opens Match if the source is animated. **Refit**
discards the current fit and fits a fresh copy; **‹ Back** removes the unbound
fit and returns to Setup. With an unanimated source, binding completes the
rig transfer and returns to Setup.

## Step 2 · Match ("New animation")

Two viewports show the source on the left and the destination on the right,
titled with their model labels and names (for example **Model A · mixamorig**
and **Model B · Nova**). Both show their skeletons; Maya's selection highlight marks
the joints you click.

- To correct a correspondence: click a source joint, click the matching
  destination joint (the *Selection* readout shows both), press **Match**.
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
- **New anim** returns to Setup and opens a file chooser to replace the
  source model with the next animation. The destination stays loaded.
- **Done** returns to Setup. **‹ Back** returns to Match to fix something.

The Animation Transfer Guide explains the backends, the baking options and
the checks RigFlow performs on every bake.

## After the transfer

The destination's facial joints and controls were never part of the body
mapping, so they are untouched: open your facial controls and keep keying.
The transferred body motion lives on the `rigflow_transfer` animation layer;
mute it to compare, lower its weight to blend, or delete it to start over.
Ctrl+Z right after a transfer removes it in one step.

Setup marks the destination animation as transferred by RigFlow. It stays
the destination when you add the next source animation.

## Tips

- Several animations for the same pair of characters: save a mapping preset
  from **Details** after the first one and load it for the next.
- **Help** gives you every guide, the repository, issue reporting and an
  *About* dialog whose environment details you can paste into bug reports.
