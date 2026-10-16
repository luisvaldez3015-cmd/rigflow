"""World-space verification; positions and distances are always centimetres."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple, Union

from maya import cmds
from maya.api import OpenMaya as om

from rigflow.scene.undo import undo_chunk

Vec3 = Tuple[float, float, float]


def sample_world_positions(nodes: Iterable[str], frames: Iterable[float]) -> Dict[str, List[Vec3]]:
    """Sample in cm regardless of scene units, restoring time even on failure."""
    result: Dict[str, List[Vec3]] = {node: [] for node in nodes}
    previous = cmds.currentTime(query=True)
    factor = om.MDistance(1.0, om.MDistance.uiUnit()).asCentimeters()
    with undo_chunk("RigFlow: sample motion"):
        try:
            for frame in frames:
                cmds.currentTime(frame, edit=True)
                for node in result:
                    xyz = cmds.xform(node, query=True, worldSpace=True, translation=True)
                    result[node].append(tuple(v * factor for v in xyz))
        finally:
            cmds.currentTime(previous, edit=True)
    return result


def _distance(a: Vec3, b: Vec3) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def bone_length_error(joints: Union[str, Iterable[str]], frames: Iterable[float]) -> float:
    """Maximum length change in cm between included parent/child joints.

    A string root expands its joint hierarchy (legacy architecture contract).
    A joint sequence measures only edges within that set: the transferred hips
    are a motion root even if an unmapped scene root is their actual parent.
    """
    if isinstance(joints, str):
        joints = [joints] + (cmds.listRelatives(joints, allDescendents=True,
                                               type="joint", fullPath=True) or [])
    nodes = {cmds.ls(j, long=True)[0] for j in joints}
    edges = []
    for node in nodes:
        parent = cmds.listRelatives(node, parent=True, fullPath=True) or []
        if parent and parent[0] in nodes:
            edges.append((parent[0], node))
    positions = sample_world_positions(nodes, frames)
    error = 0.0
    for parent, child in edges:
        lengths = [_distance(a, b) for a, b in zip(positions[parent], positions[child])]
        if lengths:
            error = max(error, max(abs(v - lengths[0]) for v in lengths))
    return error


def travel(node: str, frames: Iterable[float]) -> float:
    """Total sampled path length in cm (zero for fewer than two samples)."""
    points = sample_world_positions([node], frames)[node]
    return sum(_distance(a, b) for a, b in zip(points, points[1:]))
