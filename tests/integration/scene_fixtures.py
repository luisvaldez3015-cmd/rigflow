"""Build real Maya skeletons for integration tests.

Thin wrapper over :mod:`rigflow.scene.demo` (the Maya builder) and
:mod:`rigflow.skeleton.samples` (the pure specs), so tests, the demo scene and
the documentation all describe the same characters. Requires
``maya.standalone`` to be initialised (see ``scripts/run_tests.py``).
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Iterable, Optional, Sequence, Tuple

from maya import cmds

_UNIT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "unit")
if _UNIT_DIR not in sys.path:
    sys.path.insert(0, _UNIT_DIR)

import fixtures  # noqa: E402,F401  (pure specs shared with the unit tests)
from rigflow.scene import demo as _demo  # noqa: E402
from rigflow.skeleton.samples import custom_roles, mixamo_roles  # noqa: E402,F401

Spec = Sequence[Tuple[str, str, Tuple[float, float, float]]]

animate_jump = _demo.animate_jump


def new_scene(fps: str = "film", linear: str = "cm") -> None:
    """Fresh scene with known units (Y up, cm, 24 fps by default)."""
    cmds.file(new=True, force=True)
    cmds.currentUnit(linear=linear, time=fps)
    if cmds.upAxis(q=True, axis=True) != "y":
        cmds.upAxis(axis="y", rotateView=False)
    cmds.currentTime(1, edit=True)


def build_skeleton(
    spec: Spec,
    orient: str = "xyz",
    secondary_axis: str = "yup",
    group: Optional[str] = None,
) -> Dict[str, str]:
    """Create joints at the spec's world positions; returns ``{spec_name: node}``."""
    created = _demo.build_skeleton(spec, orient=orient, secondary_axis=secondary_axis)
    if group:
        roots = [j for n, j in created.items() if not cmds.listRelatives(j, parent=True)]
        created["__group__"] = cmds.group(roots, name=group)
    return created


def world_position(node: str, frame: Optional[float] = None) -> Tuple[float, float, float]:
    if frame is not None:
        cmds.currentTime(frame, edit=True)
    return tuple(cmds.xform(node, q=True, worldSpace=True, translation=True))  # type: ignore[return-value]


def sample(nodes: Iterable[str], frames: Iterable[float]) -> Dict[str, list]:
    """World positions of ``nodes`` at each frame (restores the current time)."""
    previous = cmds.currentTime(q=True)
    result = {node: [] for node in nodes}
    for frame in frames:
        cmds.currentTime(frame, edit=True)
        for node in result:
            result[node].append(world_position(node))
    cmds.currentTime(previous, edit=True)
    return result
