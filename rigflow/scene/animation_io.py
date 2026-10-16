"""Animation and scene-unit queries without changing the current pose."""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from maya import cmds

from rigflow.core.errors import SceneError
from rigflow.core.logging import get_logger
from rigflow.scene.undo import undo_chunk

log = get_logger(__name__)


def _expanded_nodes(nodes: Sequence[str]) -> List[str]:
    """Resolve existing nodes and DAG descendants, tolerating DG selections."""
    found = set()
    for node in nodes:
        for resolved in cmds.ls(node, long=True, objectsOnly=True) or []:
            found.add(resolved)
            if cmds.objectType(resolved, isAType="dagNode"):
                found.update(cmds.listRelatives(resolved, allDescendents=True, fullPath=True) or [])
    return sorted(found)


def _animation_curves(targets: Sequence[str]) -> List[str]:
    """Walk animation inputs, including layer blends, without crossing rig DAGs."""
    pending = []
    for target in targets:
        pending.extend(cmds.listConnections(target, source=True, destination=False) or [])
        if cmds.objExists(target) and cmds.nodeType(target).startswith("animCurve"):
            pending.append(target)
    seen = set()
    curves = set()
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        kind = cmds.nodeType(node)
        if kind.startswith("animCurve"):
            curves.add(node)
        elif kind == "pairBlend" or kind.startswith("animBlendNode") or kind in (
            "unitConversion", "blendWeighted", "mute",
        ):
            pending.extend(cmds.listConnections(node, source=True, destination=False) or [])
    return sorted(curves)


def animation_range(nodes: Sequence[str]) -> Optional[Tuple[float, float]]:
    """Return the first and last keyed times on nodes and their descendants."""
    curves = _animation_curves(_expanded_nodes(nodes))
    times = cmds.keyframe(curves, query=True, timeChange=True) if curves else []
    return (float(min(times)), float(max(times))) if times else None


def has_animation(node: str) -> bool:
    """Whether translate or rotate channels have keys, including animation layers."""
    if not cmds.objExists(node):
        return False
    plugs = [node + "." + attr for attr in (
        "translate", "translateX", "translateY", "translateZ",
        "rotate", "rotateX", "rotateY", "rotateZ",
    )
             if cmds.attributeQuery(attr, node=node, exists=True)]
    curves = _animation_curves(plugs)
    return bool(curves and cmds.keyframe(curves, query=True, keyframeCount=True))


def time_unit() -> str:
    """Return Maya's current time-unit token."""
    return cmds.currentUnit(query=True, time=True)


def linear_unit() -> str:
    """Return Maya's current linear-unit token."""
    return cmds.currentUnit(query=True, linear=True)


def up_axis() -> str:
    """Return the scene's up axis."""
    return cmds.upAxis(query=True, axis=True).lower()


def scene_fps() -> float:
    """Resolve named and numeric Maya time units to frames per second."""
    unit = time_unit()
    rates = {"game": 15, "film": 24, "pal": 25, "ntsc": 30, "show": 48,
             "palf": 50, "ntscf": 60, "hour": 1.0 / 3600, "min": 1.0 / 60,
             "sec": 1, "millisec": 1000}
    if unit in rates:
        return float(rates[unit])
    try:
        rate = float(unit[:-3]) if unit.endswith("fps") else 0.0
        if rate > 0 and math.isfinite(rate):
            return rate
    except ValueError:
        pass
    raise SceneError("Unknown Maya time unit: {}".format(unit),
                     hint="Choose a supported time unit in Maya's preferences.")


def set_playback_range(start: float, end: float) -> None:
    """Set both playback and animation bounds in one undo step."""
    if not math.isfinite(start) or not math.isfinite(end) or start > end:
        raise SceneError("Invalid playback range", hint="Use finite times with start <= end.")
    with undo_chunk("RigFlow: playback range"):
        cmds.playbackOptions(minTime=start, maxTime=end,
                             animationStartTime=start, animationEndTime=end)
