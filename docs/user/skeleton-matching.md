# Skeleton Matching Guide

RigFlow pairs the joints of the source and the destination skeleton through a
shared vocabulary of **roles** (`Hips`, `Spine`, `Spine1`, `Neck`, `Head`,
`LeftShoulder`, `LeftArm`, `LeftForeArm`, `LeftHand`, `LeftUpLeg`, `LeftLeg`,
`LeftFoot`, `LeftToeBase`, fingers, and the mirrored right side). Each skeleton
is labeled against this vocabulary on its own; the mapping is simply the
join on role. This is why two skeletons with different joint counts, names and
proportions can still be matched.

## How automatic matching works

Every joint collects evidence from two independent analyses:

1. **Name analysis** tokenises the joint name and looks for body-part keywords
   and side markers in many conventions (see *Compatibility*). It also flags
   joints that must never be mapped: end tips, twist helpers, facial joints,
   controls and props.
2. **Topology analysis** ignores names completely. It finds the hips (the first
   joint with two downward branches and one upward branch), walks the legs down
   to the feet, the spine up to the chest (the first joint whose branches spread
   left and right), the arms out to the hands and the neck up to the head. Left
   and right are decided from the rest pose; if the names clearly disagree,
   RigFlow flips the lateral axis automatically (characters facing -Z).

The two results are fused per joint:

| Situation | Result |
|-----------|--------|
| Name and topology agree | **Green**, confidence 0.95 |
| Name is ambiguous (`shoulder` = clavicle or upper arm, `leg` = thigh or shin) and topology picks one | **Green**, confidence 0.90 |
| Only the name gives a role (fingers, joints outside the main chains) | Green when the name is explicit (0.80), otherwise **Yellow** |
| Only topology gives a role (nameless `joint12` skeletons) | **Yellow**, confidence 0.65 |
| Name and topology disagree | **Yellow**; review the slot in the viewport |
| Two joints claim the same role | The stronger one keeps it; the other becomes unassigned |

Spine and neck chains are renumbered by hierarchy depth, so `spine_01…05`,
`Spine/Spine1/Spine2` and `Spine1_M/Spine2_M/Chest_M` line up as far as both
skeletons go; optional joints without a counterpart are skipped during transfer.

## Reading the definition map

| Status | Meaning | What to do |
|--------|---------|------------|
| Green | This model's joint is assigned with high confidence or manually | Nothing |
| Yellow | Automatic guess needs review | Check it in the viewport; correct if needed |
| Red outline | Required slot empty | Connect a joint |
| Solid red | Invalid, duplicated or excluded definition from a preset | Clear and reconnect it |
| Small gray outline | Optional slot empty | Leave it empty when the model lacks that bone |
| Cyan | Waiting for a scene joint selection | Select one joint, or Esc to cancel |

Required roles (Hips, Spine, Head, both arms with forearm and hand, both legs
with shin and foot) can never be excluded and must be complete on both sides.

Each panel follows its own skeleton's spine and neck chains, up to **Spine 9**
and **Neck 9**. A model with six spine joints and two neck joints shows
**Spine…Spine 5** and **Neck, Neck 1**, even when the other model has fewer.
The map keeps at least four spine slots and one neck slot; longer chains are
spaced evenly, with smaller dots and distinct click areas. Extra slots are
optional and support the same selection, Clear and Unmatch actions. Cleared
slots remain visible when their roles are detected in that skeleton.
Twist/roll helpers, facial joints, props and end tips stay hidden.

## Correcting a match by hand

In the **Match** step:

1. Click a slot or empty space in either side-by-side model panel. Its header
   highlights and Maya's main viewport isolates that model; **Bones / Mesh / Both**
   in the centre column changes its display, with joint X-ray enabled.
2. Click an empty slot on **Body** or **Hands**, then select that joint in Maya.
   The slot turns green. Esc or clicking it again cancels waiting.
3. Repeat for the other model. The selected role highlights on both maps and
   the centre Selection block shows both joints. Header counters track the 15
   required body roles. One **Body / Hands** switch controls both maps. Hover
   any slot for its role, joint and required/optional status.

You may select one joint first, then click its slot. Clicking an assigned slot
selects its scene joint; right-click **Clear** before a slot-first replacement.
A reused joint moves from its old role. Joints from the other model warn instead
of assigning. Manual edits affect only the chosen model.

**Unmatch** clears the selected role on both models; right-click **Clear**
affects just that panel. **Auto-match** preserves manual assignments and
individual clears. **… → Clear Model A / Clear Model B** confirms and resets
only that model so Auto-match can start it again. Use **… → Save preset… /
Load preset…** for the next animation between the same two skeletons. Leaving Match restores the previous main viewport and camera.

## Validation

Before the preview and transfer actions are enabled RigFlow checks:

- every required role is mapped on both sides (error);
- no joint is used by two roles (error);
- each mapped joint hangs under an expected parent, e.g. a hand under a
  forearm or arm, never under the other side (warning);
- the height ratio between the skeletons is plausible; a ratio far from 1
  usually means a cm/m unit mismatch (warning).

Errors block the transfer. Warnings are shown and left to your judgement.
