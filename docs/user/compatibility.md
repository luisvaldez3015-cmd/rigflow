# Supported Formats and Compatibility

RigFlow decides what a file contains by **inspecting the scene after import**,
never by its extension alone. A file with a mesh is not necessarily a rig, and a
joint hierarchy is not necessarily animated: the Model, Rig and Animation
sections tell you exactly what was detected.

## Maya versions

| Maya | Python | Qt | Status |
|------|--------|----|--------|
| 2024 | 3.10 | PySide2 5.15 | Primary target. Unit and integration tests run on it. |
| 2023 | 3.9 | PySide2 5.15 | Tested headless with `mayapy`. |
| 2025 / 2026 | 3.11 | PySide6 | Code is written for it (Qt shim) but not yet verified on a real installation. Please report results. |
| 2022 and older | 3.7 / 2.7 | PySide2 | Not supported. |

Windows is the development platform. macOS and Linux should work (pure Python
and Maya APIs only) but are untested.

## File formats

| Format | Import | Notes |
|--------|--------|-------|
| `.fbx` | Yes (FBX plugin) | Mixamo exports, game-engine skeletons, MotionBuilder files. Imported into a private namespace. |
| `.ma` / `.mb` | Yes | Maya scenes containing skeletons, meshes, rigs and animation. |
| Scene content | Yes | Skeletons already present in the open scene can be used as source or destination. |
| `.bvh`, `.anim`, `.abc` | No | Convert to FBX first. |

## Skeletons

### Naming conventions recognised automatically

RigFlow's name analysis understands the following vocabularies out of the box
and treats unknown names through hierarchy analysis instead:

- Mixamo / HumanIK / MotionBuilder (`mixamorig:LeftForeArm`, `Spine1`, `LeftHandIndex1`)
- Unreal Engine mannequin and MetaHuman (`pelvis`, `spine_01…05`, `clavicle_l`, `upperarm_l`, `lowerarm_l`, `thigh_l`, `calf_l`, `ball_l`, `index_01_l`)
- AdvancedSkeleton (`Root_M`, `Chest_M`, `Scapula_L`, `Shoulder_L`, `Elbow_L`, `Wrist_L`, `Hip_L`, `Knee_L`, `Ankle_L`, `ThumbFinger1_L`)
- 3ds Max Biped (`Bip01 L Thigh`, `Bip01 L Clavicle`, `Bip01 L UpperArm`)
- Unity Humanoid (`LeftUpperArm`, `LeftLowerLeg`)
- Daz Genesis (`lShldrBend`, `lForearmBend`, `abdomenLower`)
- Generic studio styles (`l_wrist_JNT`, `r_knee_JNT`, `pelvis_JNT`, `arm_L`, `hip_L`)

### Requirements for a transferable skeleton

Both skeletons must expose these 15 roles (the HumanIK minimum): Hips, Spine,
Head, and on each side Arm (upper arm), ForeArm, Hand, UpLeg (thigh), Leg
(shin), Foot. Neck, clavicles, toes, extra spine joints and fingers are
optional and transferred when both sides have them.

### Joints RigFlow deliberately ignores

These are detected and left untouched so facial rigs, props and helper joints
are never affected:

- end/tip joints (`HeadTop_End`, `LeftToe_End`, `*_tip`)
- twist/roll helpers (`upperarm_twist_01_l`, `*Roll`)
- facial joints (eyes, jaw, tongue, brows, lips, cheeks, ears, nose, teeth)
- controls and groups (`*_CTRL`, `*_grp`, `ik_*`, `fk_*`)
- accessories (weapons, props, hair, cloth, tails, wings)
- metacarpals and extra finger joints beyond the fourth phalanx

## Known limitations

- Non-humanoid skeletons (quadrupeds, creatures) are not supported in v1.
- Destination rigs whose joints are driven by animation controls (FK/IK rigs)
  receive the bake on the **joints**; baking onto controls is a later milestone.
- Scenes with mixed units or frame rates are transferred as-is; RigFlow warns
  when the height ratio between characters suggests a cm/m mismatch.
