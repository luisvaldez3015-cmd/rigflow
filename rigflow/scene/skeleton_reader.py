"""Capture Maya joint hierarchies as pure skeleton snapshots."""

from __future__ import annotations

from typing import List, Optional

from maya import cmds

from rigflow.core.errors import SceneError
from rigflow.core.logging import get_logger
from rigflow.scene.animation_io import has_animation, linear_unit, up_axis
from rigflow.scene.inspector import _joint_ancestor, _unique_name
from rigflow.scene.rest_pose import rest_pose
from rigflow.scene.undo import undo_chunk
from rigflow.skeleton.model import JointInfo, Skeleton
from rigflow.utils.strings import namespace_of, short_name

log = get_logger(__name__)


def _joints(root: str) -> List[str]:
    matches = cmds.ls(root, long=True, type="joint") or []
    if len(matches) != 1:
        raise SceneError("Skeleton root must identify one joint: {}".format(root),
                         hint="Select a joint root using its unique name or full DAG path.")
    root = matches[0]
    return [root] + sorted(cmds.listRelatives(root, allDescendents=True, type="joint",
                                            fullPath=True) or [], key=lambda n: (n.count("|"), n))


def read_skeleton(root: str, name: Optional[str] = None) -> Skeleton:
    """Read all joints at the current pose, preserving world matrix rotation entries."""
    joints = _joints(root)
    names = {j: _unique_name(j) for j in joints}
    infos = []
    for joint in joints:
        matrix = cmds.xform(joint, query=True, worldSpace=True, matrix=True)
        infos.append(JointInfo(
            name=names[joint], parent=names.get(_joint_ancestor(joint)),
            world_position=tuple(cmds.xform(joint, query=True, worldSpace=True, translation=True)),
            animated=has_animation(joint), node_type="joint",
            world_orient=tuple(float(matrix[i]) for i in (0, 1, 2, 4, 5, 6, 8, 9, 10)),
        ))
    display_name = name if name is not None else (namespace_of(joints[0]) or short_name(joints[0]))
    return Skeleton(infos, name=display_name, up_axis=up_axis(), linear_unit=linear_unit())


def read_skeleton_rest(root: str, name: Optional[str] = None,
                       stance_time: Optional[float] = None) -> Skeleton:
    """Read a rest-pose snapshot, restoring time, values and input connections."""
    with undo_chunk("RigFlow: read rest skeleton"):
        with rest_pose(_joints(root), stance_time):
            return read_skeleton(root, name)
