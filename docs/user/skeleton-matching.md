# Skeleton Matching Guide

RigFlow pairs the joints of the source and the destination skeleton through a
shared vocabulary of **roles** (`Hips`, `Spine`, `Spine1`, `Neck`, `Head`,
`LeftShoulder`, `LeftArm`, `LeftForeArm`, `LeftHand`, `LeftUpLeg`, `LeftLeg`,
`LeftFoot`, `LeftToeBase`, fingers, and the mirrored right side). Each skeleton
is labeled against this vocabulary on its own; the mapping table is simply the
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
| Name and topology disagree | **Yellow** with an explanation in the row's tooltip |
| Two joints claim the same role | The stronger one keeps it; the other becomes unassigned |

Spine and neck chains are renumbered by hierarchy depth, so `spine_01…05`,
`Spine/Spine1/Spine2` and `Spine1_M/Spine2_M/Chest_M` line up as far as both
skeletons go; extra joints on the longer chain are shown as *unavailable*.

## Reading the mapping table

| Status | Meaning | What to do |
|--------|---------|------------|
| Green | High-confidence or manual match, both joints present | Nothing |
| Yellow | Match present but needs review | Check it in the viewport; confirm or correct |
| Red | A required role is missing or the match is unreliable | Fix it before transferring |
| Gray (unavailable) | Optional role present on only one skeleton | Nothing; it is skipped |
| Purple (excluded) | You chose not to transfer this role | Re-enable it if needed |

Required roles (Hips, Spine, Head, both arms with forearm and hand, both legs
with shin and foot) can never be excluded and must be complete on both sides.

## Correcting a match by hand

1. Select the role's row in the table.
2. Click the correct joint in the Source tree and in the Destination tree.
3. Press **Link selected** (or double-click). The row turns green and is
   marked *manual*.

Manual corrections survive **Auto-match** recomputations. **Reset to automatic**
discards them explicitly. Mappings can be saved as `.rigflow.json` presets and
reloaded for the next animation between the same two skeletons.

## Validation

Before the preview and transfer actions are enabled RigFlow checks:

- every required role is mapped on both sides (error);
- no joint is used by two roles (error);
- each mapped joint hangs under an expected parent, e.g. a hand under a
  forearm or arm, never under the other side (warning);
- the height ratio between the skeletons is plausible; a ratio far from 1
  usually means a cm/m unit mismatch (warning).

Errors block the transfer. Warnings are shown and left to your judgement.
