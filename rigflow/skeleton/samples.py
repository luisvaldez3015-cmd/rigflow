"""Sample humanoid skeleton specifications.

A *spec* is a list of ``(name, parent, (x, y, z))`` tuples in centimetres,
Y up, character facing +Z, left side at +X (Maya convention), parents listed
before children. The same specs feed the unit tests, the off-screen UI
preview, the Maya demo-scene builder and the documentation, so every part of
RigFlow talks about the same characters.

The hierarchies mirror what the corresponding tools really export, including
the helper joints RigFlow must ignore (end tips, twist joints, IK helpers,
metacarpals).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from rigflow.skeleton.model import JointInfo, Skeleton

Spec = List[Tuple[str, str, Tuple[float, float, float]]]


def build_skeleton(spec: Iterable[Tuple], name: str = "", **kwargs) -> Skeleton:
    """Turn a spec into a pure :class:`Skeleton` (no Maya involved)."""
    joints = [JointInfo(name=n, parent=(p or None), world_position=tuple(pos)) for n, p, pos in spec]
    return Skeleton(joints, name=name, **kwargs)


def _swap(name: str, left: str, right: str, where: str) -> str:
    if where == "prefix":
        return right + name[len(left):] if name.startswith(left) else name
    if where == "suffix":
        return name[: -len(left)] + right if name.endswith(left) else name
    return name.replace(left, right, 1)


def _has_side(name: str, left: str, where: str) -> bool:
    if where == "prefix":
        return name.startswith(left)
    if where == "suffix":
        return name.endswith(left)
    return left in name


def mirror(spec: Spec, left_token: str, right_token: str, where: str = "any") -> Spec:
    """Right-side copies of the left-side entries (names swapped, X negated).

    ``where`` restricts the side token to the ``"prefix"``, the ``"suffix"`` or
    the ``"any"`` first occurrence, so ``l_ball_JNT`` becomes ``r_ball_JNT``.
    """
    out: Spec = []
    for name, parent, (x, y, z) in spec:
        if _has_side(name, left_token, where):
            r_name = _swap(name, left_token, right_token, where)
            r_parent = _swap(parent, left_token, right_token, where) if parent else parent
            out.append((r_name, r_parent, (-x, y, z)))
    return out


# --- Mixamo ----------------------------------------------------------------------------------


def mixamo_spec(prefix: str = "mixamorig:", fingers: bool = True, ends: bool = True) -> Spec:
    """Mixamo export: 65 joints, T-pose, 180 cm, hips at 100 cm."""
    p = prefix
    spec: Spec = [
        (p + "Hips", "", (0, 100, 0)),
        (p + "Spine", p + "Hips", (0, 110, 0)),
        (p + "Spine1", p + "Spine", (0, 122, 0)),
        (p + "Spine2", p + "Spine1", (0, 135, 0)),
        (p + "Neck", p + "Spine2", (0, 150, 0)),
        (p + "Head", p + "Neck", (0, 160, 0)),
        (p + "LeftShoulder", p + "Spine2", (5, 148, 0)),
        (p + "LeftArm", p + "LeftShoulder", (18, 148, 0)),
        (p + "LeftForeArm", p + "LeftArm", (45, 148, 0)),
        (p + "LeftHand", p + "LeftForeArm", (72, 148, 0)),
        (p + "LeftUpLeg", p + "Hips", (9, 95, 0)),
        (p + "LeftLeg", p + "LeftUpLeg", (9, 52, 0)),
        (p + "LeftFoot", p + "LeftLeg", (9, 8, 0)),
        (p + "LeftToeBase", p + "LeftFoot", (9, 2, 12)),
    ]
    if ends:
        spec.append((p + "HeadTop_End", p + "Head", (0, 180, 0)))
        spec.append((p + "LeftToe_End", p + "LeftToeBase", (9, 1, 20)))
    if fingers:
        for finger, z0 in (("Thumb", 3), ("Index", 2), ("Middle", 0), ("Ring", -2), ("Pinky", -4)):
            parent = p + "LeftHand"
            for i in range(1, 5):
                name = "{}LeftHand{}{}".format(p, finger, i)
                spec.append((name, parent, (74 + i * 3, 148 - (1 if finger == "Thumb" else 0), z0)))
                parent = name
    spec += mirror(spec, "Left", "Right")
    return spec


def mixamo_roles(prefix: str = "mixamorig:") -> Dict[str, str]:
    """Role -> joint name for :func:`mixamo_spec` (Mixamo names are the roles)."""
    return {n[len(prefix):]: n for n, _, _ in mixamo_spec(prefix=prefix) if not n.endswith("_End")}


def mixamo_mirrored_spec() -> Spec:
    """Same skeleton with the left side at negative X (character facing -Z)."""
    return [(n, par, (-x, y, z)) for n, par, (x, y, z) in mixamo_spec()]


def dense_spec(prefix: str = "dense:") -> Spec:
    """Six spines, two necks, fingers and ignored twist/face/prop/end joints."""
    p = prefix
    spec: Spec = [(p + "Hips", "", (0, 100, 0))]
    parent = p + "Hips"
    for i in range(6):
        name = p + ("Spine" if i == 0 else "Spine" + str(i))
        spec.append((name, parent, (0, 106 + i * 8, 0)))
        parent = name
    spec += [(p + "Neck", parent, (0, 152, 0)),
             (p + "Neck1", p + "Neck", (0, 158, 0)),
             (p + "Head", p + "Neck1", (0, 166, 0))]
    for name, parent, pos in mixamo_spec(prefix=p):
        if name in {p + n for n in ("Hips", "Spine", "Spine1", "Spine2", "Neck", "Head")}:
            continue
        spec.append((name, p + "Spine5" if parent == p + "Spine2" else parent, pos))
    spec += [(p + "LeftArm_twist", p + "LeftArm", (30, 148, 0)),
             (p + "RightForeArm_roll", p + "RightForeArm", (-60, 148, 0)),
             (p + "Jaw", p + "Head", (0, 161, 5)),
             (p + "LeftEye", p + "Head", (3, 169, 7)),
             (p + "weapon_prop", p + "LeftHand", (76, 148, 5))]
    return spec


def nameless_spec() -> Spec:
    """Mixamo topology with meaningless joint names (fingers and ends removed)."""
    spec = mixamo_spec(prefix="", fingers=False, ends=False)
    rename = {name: "joint{}".format(i + 1) for i, (name, _, _) in enumerate(spec)}
    return [(rename[n], rename.get(par, ""), pos) for n, par, pos in spec]


# --- Unreal Engine / MetaHuman --------------------------------------------------------------


def unreal_spec(twists: bool = True, ik: bool = True) -> Spec:
    """UE5 mannequin-style skeleton: A-pose, twist joints, IK helpers, metacarpals."""
    spec: Spec = [
        ("root", "", (0, 0, 0)),
        ("pelvis", "root", (0, 96, 0)),
        ("spine_01", "pelvis", (0, 104, 0)),
        ("spine_02", "spine_01", (0, 114, 0)),
        ("spine_03", "spine_02", (0, 126, 0)),
        ("spine_04", "spine_03", (0, 138, 0)),
        ("spine_05", "spine_04", (0, 148, 0)),
        ("neck_01", "spine_05", (0, 156, 0)),
        ("neck_02", "neck_01", (0, 162, 0)),
        ("head", "neck_02", (0, 170, 0)),
        ("clavicle_l", "spine_05", (3, 152, 0)),
        ("upperarm_l", "clavicle_l", (17, 150, 0)),
        ("lowerarm_l", "upperarm_l", (40, 125, 2)),
        ("hand_l", "lowerarm_l", (58, 105, 6)),
        ("index_metacarpal_l", "hand_l", (60, 102, 7)),
        ("thigh_l", "pelvis", (10, 92, 0)),
        ("calf_l", "thigh_l", (11, 50, 0)),
        ("foot_l", "calf_l", (11, 10, 0)),
        ("ball_l", "foot_l", (11, 3, 12)),
    ]
    for finger, z0 in (("thumb", 9), ("index", 8), ("middle", 6), ("ring", 4), ("pinky", 2)):
        parent = "index_metacarpal_l" if finger == "index" else "hand_l"
        for i in range(1, 4):
            name = "{}_0{}_l".format(finger, i)
            spec.append((name, parent, (60 + i * 3, 100 - i * 2, z0)))
            parent = name
    if twists:
        spec += [
            ("upperarm_twist_01_l", "upperarm_l", (25, 142, 1)),
            ("upperarm_twist_02_l", "upperarm_l", (32, 134, 1)),
            ("lowerarm_twist_01_l", "lowerarm_l", (46, 118, 3)),
            ("lowerarm_twist_02_l", "lowerarm_l", (52, 112, 4)),
            ("thigh_twist_01_l", "thigh_l", (10, 78, 0)),
            ("thigh_twist_02_l", "thigh_l", (10, 64, 0)),
            ("calf_twist_01_l", "calf_l", (11, 37, 0)),
            ("calf_twist_02_l", "calf_l", (11, 24, 0)),
        ]
    spec += mirror(spec, "_l", "_r", where="suffix")
    if ik:
        spec += [
            ("ik_foot_root", "root", (0, 0, 0)),
            ("ik_foot_l", "ik_foot_root", (11, 10, 0)),
            ("ik_foot_r", "ik_foot_root", (-11, 10, 0)),
            ("ik_hand_root", "root", (0, 0, 0)),
            ("ik_hand_gun", "ik_hand_root", (-58, 105, 6)),
            ("ik_hand_l", "ik_hand_gun", (58, 105, 6)),
            ("ik_hand_r", "ik_hand_gun", (-58, 105, 6)),
        ]
    return spec


# --- AdvancedSkeleton ------------------------------------------------------------------------


def advanced_skeleton_spec() -> Spec:
    """AdvancedSkeleton naming (``_M`` center, ``Scapula_L``/``Shoulder_L``, facial joints)."""
    spec: Spec = [
        ("Root_M", "", (0, 100, 0)),
        ("Spine1_M", "Root_M", (0, 112, 0)),
        ("Spine2_M", "Spine1_M", (0, 125, 0)),
        ("Chest_M", "Spine2_M", (0, 138, 0)),
        ("Neck_M", "Chest_M", (0, 152, 0)),
        ("Head_M", "Neck_M", (0, 162, 0)),
        ("HeadEnd_M", "Head_M", (0, 182, 0)),
        ("Jaw_M", "Head_M", (0, 158, 5)),
        ("Eye_L", "Head_M", (3, 166, 8)),
        ("Scapula_L", "Chest_M", (4, 150, 0)),
        ("Shoulder_L", "Scapula_L", (17, 150, 0)),
        ("Elbow_L", "Shoulder_L", (44, 150, 0)),
        ("Wrist_L", "Elbow_L", (70, 150, 0)),
        ("Cup_L", "Wrist_L", (74, 150, -3)),
        ("Hip_L", "Root_M", (9, 95, 0)),
        ("Knee_L", "Hip_L", (9, 52, 0)),
        ("Ankle_L", "Knee_L", (9, 8, 0)),
        ("Toes_L", "Ankle_L", (9, 2, 12)),
        ("ToesEnd_L", "Toes_L", (9, 1, 20)),
    ]
    for finger, z0 in (("Thumb", 3), ("Index", 2), ("Middle", 0), ("Ring", -2), ("Pinky", -4)):
        parent = "Wrist_L"
        for i in range(1, 4):
            name = "{}Finger{}_L".format(finger, i)
            spec.append((name, parent, (72 + i * 3, 150, z0)))
            parent = name
    spec += mirror(spec, "_L", "_R", where="suffix")
    return spec


# --- Custom studio naming (the brief's example destination) --------------------------------


def custom_spec() -> Spec:
    """Short character (120 cm), proportionally long arms, no clavicles or fingers."""
    spec: Spec = [
        ("root_JNT", "", (0, 0, 0)),
        ("pelvis_JNT", "root_JNT", (0, 66, 0)),
        ("spine_01_JNT", "pelvis_JNT", (0, 74, 0)),
        ("spine_02_JNT", "spine_01_JNT", (0, 84, 0)),
        ("chest_JNT", "spine_02_JNT", (0, 94, 0)),
        ("neck_JNT", "chest_JNT", (0, 102, 0)),
        ("head_JNT", "neck_JNT", (0, 110, 0)),
        ("l_shoulder_JNT", "chest_JNT", (10, 100, 0)),
        ("l_elbow_JNT", "l_shoulder_JNT", (34, 100, 0)),
        ("l_wrist_JNT", "l_elbow_JNT", (60, 100, 0)),
        ("l_hip_JNT", "pelvis_JNT", (7, 62, 0)),
        ("l_knee_JNT", "l_hip_JNT", (7, 34, 0)),
        ("l_ankle_JNT", "l_knee_JNT", (7, 6, 0)),
        ("l_ball_JNT", "l_ankle_JNT", (7, 1, 9)),
    ]
    spec += mirror(spec, "l_", "r_", where="prefix")
    return spec


def custom_roles() -> Dict[str, str]:
    """Role -> joint name for :func:`custom_spec`."""
    roles = {
        "Hips": "pelvis_JNT", "Spine": "spine_01_JNT", "Spine1": "spine_02_JNT",
        "Spine2": "chest_JNT", "Neck": "neck_JNT", "Head": "head_JNT",
    }
    for side, prefix in (("Left", "l_"), ("Right", "r_")):
        roles.update({
            side + "Arm": prefix + "shoulder_JNT", side + "ForeArm": prefix + "elbow_JNT",
            side + "Hand": prefix + "wrist_JNT", side + "UpLeg": prefix + "hip_JNT",
            side + "Leg": prefix + "knee_JNT", side + "Foot": prefix + "ankle_JNT",
            side + "ToeBase": prefix + "ball_JNT",
        })
    return roles


SAMPLES = {
    "mixamo": mixamo_spec,
    "unreal": unreal_spec,
    "advanced_skeleton": advanced_skeleton_spec,
    "custom": custom_spec,
    "nameless": nameless_spec,
    "dense": dense_spec,
}
