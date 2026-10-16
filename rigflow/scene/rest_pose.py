"""Temporarily put an animated skeleton back into its rest (bind) pose.

HumanIK captures the *stance pose* of a skeleton when it is characterised, and
the matrix-based fallback needs rest orientations as well. Imported animations
already drive the joints, so this module:

1. optionally moves the time slider to a *stance frame* (default: the first
   frame of the clip, usually a grounded pose);
2. records and disconnects every input connection on the joints' translate,
   rotate and scale channels;
3. restores the bind pose from the skeleton's ``dagPose`` node when one exists,
   otherwise zeroes the rotations (skeletons exported from Maya or Mixamo keep
   their T-pose in ``jointOrient``, so zero rotation *is* the bind pose);
4. yields, then restores the recorded values and reconnects everything.

Use it inside an :func:`rigflow.scene.undo.undo_chunk` so a failure halfway is
still a single undo step.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from maya import cmds

from rigflow.core.logging import get_logger

log = get_logger(__name__)

TRANSFORM_CHANNELS = (
    "translate", "translateX", "translateY", "translateZ",
    "rotate", "rotateX", "rotateY", "rotateZ",
    "scale", "scaleX", "scaleY", "scaleZ",
)


def bind_pose_node(joints: Iterable[str]) -> Optional[str]:
    """Return the ``dagPose`` bind pose connected to any of ``joints``, if any."""
    for joint in joints:
        poses = cmds.listConnections(joint, type="dagPose") or []
        for pose in poses:
            if cmds.getAttr(pose + ".bindPose"):
                return pose
    return None


def _settable(plug: str) -> bool:
    return cmds.objExists(plug) and not cmds.getAttr(plug, lock=True)


def _disconnect_inputs(joints: List[str]) -> Tuple[List[Tuple[str, str]], Dict[str, object]]:
    connections: List[Tuple[str, str]] = []
    values: Dict[str, object] = {}
    for joint in joints:
        for channel in TRANSFORM_CHANNELS:
            plug = "{}.{}".format(joint, channel)
            if not cmds.objExists(plug):
                continue
            sources = cmds.listConnections(plug, source=True, destination=False, plugs=True) or []
            for source in sources:
                connections.append((source, plug))
                cmds.disconnectAttr(source, plug)
            if "X" in channel or "Y" in channel or "Z" in channel:
                values[plug] = cmds.getAttr(plug)
    return connections, values


def _apply_bind_pose(joints: List[str]) -> str:
    pose = bind_pose_node(joints)
    if pose:
        try:
            cmds.dagPose(joints, restore=True, name=pose)
            return "dagPose:{}".format(pose)
        except RuntimeError as exc:  # members missing from the pose, locked attrs...
            log.warning("Could not restore %s (%s); falling back to zero rotations", pose, exc)
    for joint in joints:
        for axis in "XYZ":
            plug = "{}.rotate{}".format(joint, axis)
            if _settable(plug):
                cmds.setAttr(plug, 0.0)
    return "zero-rotation"


@contextmanager
def rest_pose(joints: Iterable[str], stance_time: Optional[float] = None) -> Iterator[str]:
    """Context manager: joints are in rest pose inside the block.

    Yields a string describing how the pose was obtained (``"dagPose:<node>"``
    or ``"zero-rotation"``) so callers can report it to the user.
    """
    joints = [j for j in joints if cmds.objExists(j)]
    previous_time = cmds.currentTime(q=True)
    if stance_time is not None:
        cmds.currentTime(stance_time, edit=True)
    connections, values = _disconnect_inputs(joints)
    try:
        method = _apply_bind_pose(joints)
        log.debug("Rest pose applied to %d joints via %s", len(joints), method)
        yield method
    finally:
        for plug, value in values.items():
            if _settable(plug):
                try:
                    cmds.setAttr(plug, value)
                except RuntimeError:  # pragma: no cover - defensive
                    log.warning("Could not restore %s", plug)
        for source, plug in connections:
            if cmds.objExists(source) and cmds.objExists(plug):
                cmds.connectAttr(source, plug, force=True)
        cmds.currentTime(previous_time, edit=True)
