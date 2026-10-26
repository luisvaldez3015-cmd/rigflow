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

- **Mesh**: detected polygon geometry.
- **Rig**: detected skeleton.
- **Anim**: detected animation.

Each slot says **✓ Detected** or **None**; hover it for details such as skinning,
root joint, naming convention, required roles or frame range. Slots fill
automatically when you add the model. **Replace…**, or dropping a file on a
card, replaces the entire model. **Remove** removes the model and its owned
import; models taken from the existing Maya scene remain in that scene.

Press the small **+ · Add the second model** below the first card to add
**Model B**. The two model cards sit side by side. Two process cards below
them always show what is available, its direction and any blocking reason:

- **Transfer rig**: **Start Rig** copies a skinned source skeleton and its
  weights onto a mesh-only destination. Rest-pose mesh similarity must be at
  least **80%**. The percentage, bar and **Meshes match / Meshes don't match**
  verdict explain the comparison. **Differs around: Head**, for example,
  identifies a region to polish manually after binding.
- **Transfer animation**: **Start Match** is available when the source has
  authored animation and the destination has a rig. A mesh-only destination
  needs Transfer rig first. A joints-only source can transfer animation but
  cannot supply skin weights for rig transfer.
- Both models animated: Model A is the default source. **Swap direction**
  makes Model B the source instead.
- Unavailable processes stay visible with disabled buttons and a reason.

Starting the plan matches the joints automatically. The step indicator updates
to the proposed process.

## Rig · When the destination has no skeleton

RigFlow copies the source skeleton and fits it to the destination mesh. The
viewport isolates the mesh and fitted skeleton; the line below shows scale
and joint count. Move joints in Maya if needed, then press **Bind skin**.
This copies the source skin weights and opens Match if the source is animated.
Identical topology copies weights exactly by vertex index; different topology
uses the nearest surface and interpolates weights. Position and uniform scale
differences are normalised. Different regions are a starting point: polish
their weights by hand. **Refit**
discards the current fit and fits a fresh copy; **Back** removes the unbound
fit and returns to Setup. With an unanimated source, binding completes the
rig transfer and returns to Setup.

## Step 2 · Match (Character definition)

Define **Model A** and **Model B** on two maps shown side by side. Each header
shows the model's Setup identity, transfer direction, name and required-role
count (15/15 turns green). Click a slot or the empty area of a panel to make
that model active: its header turns cyan and Maya's main viewport isolates
and frames it with joint X-ray on. Clicking empty space also cancels waiting.

The figures have no label columns or leader lines. Small **R / L** hints use
the character's orientation (right is screen-left); hover a slot for its role,
full joint name (or **not connected**) and required/optional status. Smaller
slots (extra spines, shoulders, neck, toes and fingers) are optional.

Spine and neck slots adapt independently to each model: six spine joints show
**Spine…Spine 5**, and two neck joints show **Neck, Neck 1**. Longer chains use
smaller, evenly spaced dots (up to Spine 9 / Neck 9); hover for the slot name
and joint. Every extra slot supports the same selection and matching actions.
The map always keeps four spine slots and one neck slot available. Twist/roll
helpers, facial joints, props and end tips are ignored.

The centre column contains **Auto-match**, **Unmatch**, a shared **Body / Hands**
switch, and **Selection** with the selected role and both model joints. The
selected role has a thin cyan ring on both maps. Long scene names are shortened;
hover the selection text or model header to read the full name. **Connected /
Review / Missing** counts combine both models, including optional connections;
Missing counts required roles only, and Review includes invalid definitions.
Use **Bones / Mesh / Both** to change the main viewport display (Both by default).
Leaving Match restores its previous isolation, display flags and camera framing.

- Click an empty slot, then select its joint in Maya. Cyan means waiting;
  **Esc** or clicking the same slot again cancels. Alternatively, select one
  joint first and click its slot to assign it immediately.
- Green means assigned; yellow asks you to review an automatic guess. A red
  outline means a required slot is empty; solid red means an invalid definition.
  Click an assigned slot to select its joint, or right-click for **Clear /
  Select in scene** on that model only. To replace it, clear it first or select
  the replacement joint before clicking.
- A joint used by another role moves to the new role. A joint belonging to
  the other model produces a warning and is never assigned while waiting.
- **Unmatch** clears the selected role on both models. It is available only
  when that role has a joint on at least one model.
- **Auto-match** keeps manual assignments and individually cleared slots.
  **…** contains **Load preset… / Save preset… / Clear Model A / Clear Model B**.
  Clearing a model asks for confirmation, resets only its definition and lets
  Auto-match start that definition again.

The status line points to the next missing required role. **Transfer** is
enabled when both models have all required roles and validation has no errors.
Transfer still bakes onto the destination joints, using HumanIK where available.
Model labels retain their Setup identity if you swap the transfer direction.

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
- **Done** returns to Setup. **Back** returns to Match to fix something.

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
  from **…** in Match after the first one and load it for the next.
- **Help** gives you every guide, the repository, issue reporting and an
  *About* dialog whose environment details you can paste into bug reports.
