"""Shared layer creation, deterministic baking and Euler filtering."""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from maya import cmds

from rigflow.scene.undo import undo_chunk


def unique_layer_name(base: str) -> str:
    """Return an unused node name without renaming an existing layer."""
    name = base
    index = 1
    while cmds.objExists(name):
        name = "{}_{}".format(base, index)
        index += 1
    return name


def create_override_layer(name: str) -> str:
    """Create an empty override layer; do not pre-add joints for HIK bake."""
    with undo_chunk("RigFlow: create bake layer"):
        return cmds.animLayer(unique_layer_name(name), override=True)


def bake_joints(joints: Sequence[str], frame_range: Tuple[float, float],
                sample_by: float, attributes: Sequence[str], layer: Optional[str] = None) -> None:
    """Bake explicit channels without sparse reduction or keys outside range."""
    if not joints or not attributes:
        return
    options = {"destinationLayer": layer} if layer else {}
    with undo_chunk("RigFlow: bake joints"):
        cmds.bakeResults(list(joints), time=frame_range, sampleBy=sample_by,
                         attribute=list(attributes), simulation=True,
                         disableImplicitControl=True, preserveOutsideKeys=True,
                         sparseAnimCurveBake=False, **options)


def euler_filter(joints: Sequence[str], layer: Optional[str] = None,
                 frame_range: Optional[Tuple[float, float]] = None) -> None:
    """Filter baked rotations, restricting to the new layer/range when supplied."""
    curves = set()
    for joint in joints:
        for attr in ("rx", "ry", "rz"):
            if layer:
                curve = cmds.animLayer(layer, query=True, findCurveForPlug=joint + "." + attr)
                if curve:
                    curves.update([curve] if isinstance(curve, str) else curve)
            else:
                curves.update(cmds.keyframe(joint, attribute=attr, query=True, name=True) or [])
    if curves:
        with undo_chunk("RigFlow: Euler filter"):
            options = {"startTime": frame_range[0], "endTime": frame_range[1]} if frame_range else {}
            cmds.filterCurve(sorted(curves), filter="euler", **options)
