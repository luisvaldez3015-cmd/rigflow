# RigFlow User Guide

RigFlow transfers body animation from one skeleton to another inside Maya,
even when the two characters have different proportions, joint names and
hierarchies. The workflow is always the same:

**Import → Match → Preview → Transfer → keep animating.**

## 1. Open RigFlow

Click the **RigFlow** shelf button (see the Installation Guide) or run:

```python
import rigflow
rigflow.launch()
```

The main window has three sections. You can dock it like any Maya panel.

## 2. Choose the destination

### A · Model (optional)

The destination character's geometry. Select the mesh in Maya and press
**Use selection**, or drop / browse an `.fbx`, `.ma` or `.mb` file. RigFlow
reports the mesh count, vertex count and whether it is skinned. Geometry is
optional: the transfer works on the skeleton. It is useful for the previews
and to find the rig automatically (press **Use selection** in the Rig section
with a skinned mesh selected).

### B · Rig (required)

The skeleton that will receive the animation. Select its root joint (or a
skinned mesh) and press **Use selection**, or import a file. RigFlow shows:

- the root, the joint count and the naming convention it recognised;
- how many of the 15 required roles it could identify;
- notes about joints it ignored on purpose (facial, twist, controls).

A green **Validated** badge means the rig is ready. **Needs attention** lists
the roles it could not find; you can still fix them by hand in the matching
workspace.

## 3. Add an animation

### C · Animation

- **Add Animation** imports an `.fbx` / `.ma` / `.mb` file (Mixamo exports,
  game skeletons, MotionBuilder files...). The file goes into its own
  namespace so it never clashes with your character.
- **From scene…** uses an animated skeleton that is already in the scene.

Each clip appears in the list with its naming convention, frame range,
frame count and status:

| Status | Meaning |
|--------|---------|
| Imported | Loaded, no destination rig yet |
| Ready to transfer | Mapping complete, no errors |
| Needs review | Mapping has red rows or validation errors |
| Previewing | Live retarget connected, nothing baked |
| Transferred | Baked onto the destination |

You can keep adding clips; each one keeps its own mapping. Use the row
actions to **Edit mapping**, **Review**, **Transfer**, **Replace** the source
file or **Remove** the clip (which also deletes its imported nodes).

## 4. Match the skeletons

Adding a clip opens the matching workspace automatically.

- Left and right panels preview the source and the destination.
- The **Source hierarchy** and **Destination hierarchy** trees show the
  joints. Filter boxes help with big skeletons.
- The **Joint mapping** table has one row per role: status, source joint,
  destination joint, confidence, manual marker and an *Exclude* checkbox.
  Hover a row for the reasoning behind the match.
- Selecting a row highlights both joints and draws a link between them.

Green rows are confident, yellow rows deserve a look, red rows block the
transfer, gray rows are optional roles one skeleton does not have.

To correct a row: select it, click the right joint in each tree, press
**Link selected**. The row becomes green and *manual*. **Auto-match**
recomputes everything else but keeps your corrections; **Reset to automatic**
discards them. **Save preset…** stores the mapping as `.rigflow.json` for the
next clip between the same two characters.

The strip under the table shows counts per status and the validation result.
**Review Animation** is enabled as soon as there are no errors.
See the Skeleton Matching Guide for the details of how matching works.

## 5. Review

The review view connects the live retarget (HumanIK) so the destination
follows the source as you **Play**, **Pause**, **Stop** or scrub the
timeline. Nothing is written yet. Warnings from the mapping are listed under
the viewport.

- **Back to mapping** returns to the workspace to fix something.
- **Bake to animation layer** (on by default) keeps your existing animation safe.
- **Confirm / Add Animation** bakes the motion onto the destination joints and
  returns to the main window, where the clip shows **Transferred**.

The Animation Transfer Guide explains the backends, the baking options and
the checks RigFlow performs on every bake.

## 6. Keep animating

The destination's facial joints and controls were never part of the body
mapping, so they are untouched: open your facial controls and keep keying.
The transferred body motion lives on the `rigflow_transfer` animation layer;
mute it to compare, lower its weight to blend, or delete it to start over.
Ctrl+Z right after a transfer removes it in one step.

## Shortcuts and tips

- **Help** menu: every guide, the repository, issue reporting and an About
  dialog with the environment details to paste into bug reports.
- **Help → Create demo scene** builds two ready-made characters so you can try
  the full workflow without downloading anything.
- Several animations for the same character: save a mapping preset after the
  first one and load it for the next.
