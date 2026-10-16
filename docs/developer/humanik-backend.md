# HumanIK backend — verified programmatic pipeline

_Source: feasibility spike run on 2026-10-16 with `mayapy` from Maya 2024
(Python 3.10.8) and Maya 2023 (Python 3.9.7). Both versions behaved identically._

This page records **what actually works** when driving HumanIK (HIK) from
Python without opening its UI, what silently fails, and the rules the
`rigflow.retargeting.hik` backend must follow. Everything below was measured,
not assumed.

## Result in one paragraph

Two procedurally built skeletons with different proportions (180 cm vs 120 cm),
different names (`mixamorig:*` vs `pelvis_JNT`, `l_shoulder_JNT`...) and different
joint orientations (`oj=xyz` vs `oj=yzx`) were characterised, connected
source-to-destination and baked over 48 frames in about 0.4 s. Destination bone
lengths stayed constant (max error 0.00014 cm), the hips followed the jump arc
scaled by the hip-height ratio (2/3), elbows bent, and baking onto an override
animation layer preserved all 138 pre-existing animation curves on the destination.

## Required plugins and MEL sources

```python
for plugin in ("mayaHIK", "mayaCharacterization", "retargeterNodes"):
    if not cmds.pluginInfo(plugin, q=True, loaded=True):
        cmds.loadPlugin(plugin)
for script in ("hikGlobalUtils.mel", "hikDefinitionOperations.mel", "hikInputSourceUtils.mel"):
    mel.eval('source "%s";' % script)
```

`hikUtils.mel` does not exist and must not be sourced. `hikCharacterControlsUI.mel`
is not needed.

## Characterisation (per skeleton, in rest pose)

```python
character = mel.eval('hikCreateCharacter("%s")' % name)
mel.eval('hikSetCurrentCharacter("%s")' % character)
for slot, joint in slot_to_joint.items():            # slot = RigFlow role name
    slot_id = int(mel.eval('hikGetNodeIdFromName("%s")' % slot))
    mel.eval('setCharacterObject("%s","%s",%d,0)' % (joint, character, slot_id))
    assert mel.eval('hikGetSkNode("%s",%d)' % (character, slot_id)) == joint
mel.eval('hikCharacterLock("%s",1,1)' % character)   # captures the stance pose
```

Rules:

1. **The skeleton must be in its rest (T/A) pose when `hikCharacterLock` runs.**
   HIK captures the stance pose at that moment. For an animated source,
   RigFlow temporarily puts the skeleton in its bind pose (see below) before
   characterising and restores the animation afterwards.
2. `setCharacterObject` (alias of `hikSetCharacterObject`, defined in
   `hikDefinitionUtils.mel`) is the only assignment call that also captures the
   per-joint stance offsets. Plain `connectAttr(joint.message, character.Hips)`
   connects the joint but leaves the offsets at zero: **do not use it**.
3. `characterizationToolUICmd -edit -characternodeassign ...` does nothing in
   standalone mode (no error, no assignment). Do not use it.
4. The 15 required slots must be present: Hips, Spine, Head, Left/Right
   Arm, ForeArm, Hand, UpLeg, Leg, Foot. Optional slots (Shoulder, ToeBase,
   Neck, Spine1+, fingers) can be omitted on either side; retargeting still works.
5. Slot names are exactly RigFlow's role names. IDs are resolved at runtime
   with `hikGetNodeIdFromName`; never hardcode them. Reference values seen:
   Hips 1, LeftUpLeg 2, LeftLeg 3, LeftFoot 4, RightUpLeg 5, RightLeg 6,
   RightFoot 7, Spine 8, LeftArm 9, LeftForeArm 10, LeftHand 11, RightArm 12,
   RightForeArm 13, RightHand 14, Head 15, LeftToeBase 16, RightToeBase 17,
   LeftShoulder 18, RightShoulder 19, Neck 20, Spine1 23, Spine2 24.

### Validation is up to RigFlow

`characterizationToolUICmd -query -curcharstatus` and
`hikIsCharacterizationInValidOrWarningState()` return the same "valid" answer
for a complete character, an empty character and a Hips-only character in
standalone mode. `hikIsCharacterValid` and `hikCharacterizeNode` do not exist.
Therefore RigFlow validates a characterisation itself:

- every required role assigned and readable back through `hikGetSkNode`;
- `character.InputCharacterizationLock` is true after locking;
- after connecting the retarget, the destination hips actually move when the
  source moves (numeric check on a couple of frames) before offering a bake.

## Retargeting

```python
cmds.optionVar(iv=("hikRetargetUsingRig", 0))
mel.eval('hikSetCharacterInput("%s","%s")' % (destination_character, source_character))
```

This creates the `HIKRetargeterNode`, an `HIKSK2State` reading the source and an
`HIKState2SK` writing the destination joints. While connected, the destination
follows the source live, which is what the **preview** uses. No control rig is
created or needed.

## Baking

```python
cmds.bakeResults(
    destination_joints, time=(start, end), sampleBy=1,
    attribute=["tx", "ty", "tz", "rx", "ry", "rz"],
    simulation=True, disableImplicitControl=True,
    preserveOutsideKeys=True, sparseAnimCurveBake=False,
    bakeOnOverrideLayer=True,          # non-destructive default
)
```

- `bakeOnOverrideLayer=True` or `destinationLayer=cmds.animLayer(name, override=True)`
  with an **empty** layer both work and preserve existing curves (muting the
  layer brings the previous animation back exactly).
- **Never** add the joints to the layer beforehand with
  `animLayer(edit=True, addSelectedObjects=True)`: the active override layer
  then imposes a constant pose and the bake records 48 identical keys (72 cm
  error in the spike). Counting keys is not proof of success; RigFlow compares
  sampled positions before/after baking.
- `hikBakeCharacter(0)` also works but depends on the current character and
  persistent option variables; the explicit `bakeResults` call is preferred.

## Cleanup

After baking, delete only the nodes RigFlow created (track them by name at
creation time; do not delete every HIK node in a shared scene):
`HIKCharacterNode`, `HIKProperty2State`, `HIKRetargeterNode`, `HIKSK2State`,
`HIKSolverNode`, `HIKState2SK`. Animation layer blend nodes must stay.

## Putting an animated source in its rest pose

HIK needs the stance pose at characterisation time, but an imported Mixamo or
FBX animation already drives the joints. RigFlow's `scene.rest_pose` context
manager will:

1. record every animation curve connection on the source joints;
2. disconnect them;
3. restore the bind pose: `dagPose(restore=True, bindPose=True)` when the
   skeleton has a `bindPose` node, otherwise set `rotate = (0,0,0)` on every
   joint (skeletons exported from Maya and Mixamo store the T-pose in
   `jointOrient`, so zero rotation is the bind pose);
4. yield for characterisation;
5. reconnect the curves, inside the same undo chunk.

## Fallback without HIK

A 31-line matrix-based prototype (rest-pose rotation delta re-expressed in the
destination's rest frame, root translation scaled by hip height) matched HIK to
within 0.0001 cm on the spike motion, while naively copying local Euler values
produced errors up to 88 cm. The fallback is viable for one-to-one mappings in
compatible rest poses; it has no IK, floor contact, twist distribution or
chain-length adaptation. It is the backend of last resort when the HIK plugins
are unavailable, and it must be labeled as such in the UI.
