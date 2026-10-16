"""Build a reproducible demo scene inside Maya.

The demo contains everything the RigFlow workflow needs and nothing that
cannot be redistributed:

* **Source**: a Mixamo-style skeleton (``mixamorig:*``, 180 cm) performing a
  keyed jump over frames 1–48 (hips arc, arm swing, knee bend, head turn).
* **Destination**: a short character (120 cm) with studio-style joint names
  (``pelvis_JNT``, ``l_shoulder_JNT``...), a blocky proxy mesh skinned to it,
  and a tiny facial setup (``jaw_JNT``, eye joints and a ``jaw_CTRL`` NURBS
  control) that RigFlow must leave untouched.

Used by the integration tests, the in-Maya UI checks, the trailer and the
*Help → Create demo scene* action, so the examples shown anywhere are
reproducible by anyone with Maya.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from maya import cmds

from rigflow.core.logging import get_logger
from rigflow.scene.undo import undo_chunk
from rigflow.skeleton import samples
from rigflow.utils import math3d

log = get_logger(__name__)

Spec = Sequence[Tuple[str, str, Tuple[float, float, float]]]


@dataclass
class DemoScene:
    """Names of the nodes the demo created."""

    source_root: str
    destination_root: str
    source_joints: Dict[str, str] = field(default_factory=dict)
    destination_joints: Dict[str, str] = field(default_factory=dict)
    destination_mesh: Optional[str] = None
    facial_joints: List[str] = field(default_factory=list)
    facial_controls: List[str] = field(default_factory=list)
    frame_range: Tuple[int, int] = (1, 48)


# --- skeleton construction -------------------------------------------------------------------


def build_skeleton(
    spec: Spec,
    orient: str = "xyz",
    secondary_axis: str = "yup",
) -> Dict[str, str]:
    """Create joints at the spec's world positions; return ``{spec_name: node}``.

    Joints are oriented with ``cmds.joint(oj=...)`` so the bind pose is
    "all rotations zero", exactly like a Maya or Mixamo export. Different
    ``orient``/``secondary_axis`` values give different local axes, which is
    what makes the demo a real retargeting test.
    """
    created: Dict[str, str] = {}
    roots: List[str] = []
    for name, parent, position in spec:
        namespace = name.rsplit(":", 1)[0] if ":" in name else None
        if namespace and not cmds.namespace(exists=":" + namespace):
            cmds.namespace(add=namespace)
        cmds.select(clear=True)
        joint = cmds.joint(name=name, position=position, absolute=True)
        if parent:
            joint = cmds.parent(joint, created[parent])[0]
        else:
            roots.append(joint)
        created[name] = joint
    for root in roots:
        cmds.joint(root, edit=True, orientJoint=orient, secondaryAxisOrient=secondary_axis,
                   children=True, zeroScaleOrient=True)
    for name, joint in list(created.items()):
        matches = cmds.ls(joint)
        if len(matches) == 1:
            created[name] = matches[0]
    return created


def animate_jump(created: Dict[str, str], roles: Dict[str, str], start: int = 1, end: int = 48) -> None:
    """Key a visually unambiguous jump on a built skeleton.

    Hips follow an arc up and forward and twist; arms swing, elbows and knees
    bend, the spine leans and the head turns. Every joint gets rotation keys
    at ``start`` so each one carries animation curves like an FBX import.
    """
    hips = created[roles["Hips"]]
    base = cmds.xform(hips, q=True, worldSpace=True, translation=True)
    span = float(end - start)
    keys = sorted({start, start + int(span * 0.25), start + int(span * 0.5), start + int(span * 0.75), end})

    def key(node: str, attr: str, value: float, frame: int) -> None:
        cmds.setKeyframe(node, attribute=attr, value=value, time=frame,
                         inTangentType="linear", outTangentType="linear")

    for frame in keys:
        t = (frame - start) / span
        key(hips, "translateX", base[0], frame)
        key(hips, "translateY", base[1] + 45.0 * math.sin(math.pi * t), frame)
        key(hips, "translateZ", base[2] + 70.0 * t, frame)
        key(hips, "rotateY", 20.0 * math.sin(2 * math.pi * t), frame)

    swings = (
        ("LeftArm", "rotateZ", 45.0), ("RightArm", "rotateZ", -45.0),
        ("LeftForeArm", "rotateY", 40.0), ("RightForeArm", "rotateY", -40.0),
        ("LeftLeg", "rotateX", 60.0), ("RightLeg", "rotateX", 60.0),
        ("LeftUpLeg", "rotateX", -30.0), ("RightUpLeg", "rotateX", -30.0),
        ("Spine", "rotateX", 15.0), ("Head", "rotateY", 25.0),
    )
    for role, attr, amplitude in swings:
        node = created.get(roles.get(role, ""))
        if not node:
            continue
        for frame in keys:
            t = (frame - start) / span
            key(node, attr, amplitude * math.sin(math.pi * t), frame)

    for node in created.values():
        cmds.setKeyframe(node, attribute=["rotateX", "rotateY", "rotateZ"], time=start, insertBlend=False)
    cmds.playbackOptions(minTime=start, maxTime=end, animationStartTime=start, animationEndTime=end)
    cmds.currentTime(start, edit=True)


# --- proxy mesh and facial setup --------------------------------------------------------------


def _bone_segments(created: Dict[str, str], spec: Spec) -> List[Tuple[str, str]]:
    """``(parent_joint, child_joint)`` pairs that deserve a proxy block."""
    pairs = []
    for name, parent, _ in spec:
        # Skip the ground root: a pillar from the origin to the hips would stay
        # behind while the character jumps.
        if parent and not name.startswith("root") and not parent.startswith("root"):
            pairs.append((created[parent], created[name]))
    return pairs


def build_proxy_mesh(created: Dict[str, str], spec: Spec, name: str = "destination_body_GEO") -> str:
    """Blocky mannequin: one cylinder per bone plus a head sphere, skinned to the joints."""
    pieces: List[Tuple[str, str, int]] = []  # (transform, joint to follow, vertex count)
    for parent, child in _bone_segments(created, spec):
        start = cmds.xform(parent, q=True, worldSpace=True, translation=True)
        end = cmds.xform(child, q=True, worldSpace=True, translation=True)
        length = math3d.distance(start, end)
        if length < 1e-3:
            continue
        axis = math3d.normalize(math3d.sub(end, start))
        radius = max(2.0, min(6.0, length * 0.18))
        piece = cmds.polyCylinder(axis=list(axis), height=length, radius=radius,
                                  subdivisionsAxis=10, subdivisionsHeight=1, constructionHistory=False)[0]
        cmds.xform(piece, worldSpace=True, translation=math3d.lerp(start, end, 0.5))
        pieces.append((piece, parent, cmds.polyEvaluate(piece, vertex=True)))
    head = [j for n, j in created.items() if "head" in n.lower()]
    if head:
        pos = cmds.xform(head[0], q=True, worldSpace=True, translation=True)
        sphere = cmds.polySphere(radius=9.0, subdivisionsAxis=12, subdivisionsHeight=10,
                                 constructionHistory=False)[0]
        cmds.xform(sphere, worldSpace=True, translation=(pos[0], pos[1] + 7.0, pos[2]))
        pieces.append((sphere, head[0], cmds.polyEvaluate(sphere, vertex=True)))
    if not pieces:
        raise RuntimeError("No bone segments to build a proxy mesh from")
    mesh = cmds.polyUnite([p[0] for p in pieces], constructionHistory=False, name=name)[0]
    cmds.delete(mesh, constructionHistory=True)
    joints = [j for n, j in created.items() if cmds.nodeType(j) == "joint"]
    skin = cmds.skinCluster(joints, mesh, toSelectedBones=True, bindMethod=0, maximumInfluences=1,
                            obeyMaxInfluences=True, normalizeWeights=1,
                            name=name.replace("_GEO", "_skinCluster"))[0]
    # Rigid one-bone binding per block (polyUnite keeps input vertex order): every
    # cylinder follows the joint at its root, so the mannequin reads clearly during
    # playback instead of smearing between neighbouring limbs.
    offset = 0
    for _, joint, count in pieces:
        cmds.skinPercent(skin, "{}.vtx[{}:{}]".format(mesh, offset, offset + count - 1),
                         transformValue=[(joint, 1.0)])
        offset += count
    return mesh


def build_facial_setup(head_joint: str) -> Tuple[List[str], List[str]]:
    """Jaw and eye joints under the head plus a NURBS control driving the jaw.

    Returns ``(facial_joints, facial_controls)``. RigFlow must never key these.
    """
    head_pos = cmds.xform(head_joint, q=True, worldSpace=True, translation=True)
    cmds.select(clear=True)
    jaw = cmds.joint(name="jaw_JNT", position=(head_pos[0], head_pos[1] + 2.0, head_pos[2] + 4.0))
    jaw = cmds.parent(jaw, head_joint)[0]
    cmds.select(clear=True)
    jaw_end = cmds.joint(name="jaw_end_JNT", position=(head_pos[0], head_pos[1] - 3.0, head_pos[2] + 9.0))
    jaw_end = cmds.parent(jaw_end, jaw)[0]
    eyes = []
    for side, x in (("l", 3.0), ("r", -3.0)):
        cmds.select(clear=True)
        eye = cmds.joint(name="{}_eye_JNT".format(side),
                         position=(head_pos[0] + x, head_pos[1] + 8.0, head_pos[2] + 7.0))
        eyes.append(cmds.parent(eye, head_joint)[0])
    control = cmds.circle(name="jaw_CTRL", normal=(0, 0, 1), radius=4.0, constructionHistory=False)[0]
    cmds.xform(control, worldSpace=True, translation=(head_pos[0], head_pos[1] - 6.0, head_pos[2] + 12.0))
    group = cmds.group(control, name="jaw_CTRL_grp")
    cmds.parent(group, head_joint)
    cmds.orientConstraint(control, jaw, maintainOffset=True)
    return [jaw, jaw_end] + eyes, [control]


# --- entry point ------------------------------------------------------------------------------------


def build_demo_scene(
    animate: bool = True,
    with_mesh: bool = True,
    with_face: bool = True,
    new_scene: bool = False,
) -> DemoScene:
    """Create the demo characters in the current (or a new) scene."""
    if new_scene:
        cmds.file(new=True, force=True)
    with undo_chunk("RigFlow: build demo scene"):
        source_spec = samples.mixamo_spec()
        destination_spec = samples.custom_spec()
        source = build_skeleton(source_spec, orient="xyz")
        destination = build_skeleton(destination_spec, orient="yzx")
        # Offset the source so both characters are visible side by side.
        source_root = source[source_spec[0][0]]
        cmds.xform(source_root, worldSpace=True, relative=True, translation=(-120.0, 0.0, 0.0))

        demo = DemoScene(
            source_root=source_root,
            destination_root=destination[destination_spec[0][0]],
            source_joints=source,
            destination_joints=destination,
        )
        if with_face:
            demo.facial_joints, demo.facial_controls = build_facial_setup(destination["head_JNT"])
        if with_mesh:
            demo.destination_mesh = build_proxy_mesh(destination, destination_spec)
        if animate:
            animate_jump(source, samples.mixamo_roles(), *demo.frame_range)
        cmds.select(clear=True)
    log.info("Demo scene built: source %s, destination %s", demo.source_root, demo.destination_root)
    return demo
