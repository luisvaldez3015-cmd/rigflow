"""Matrix fallback for compatible rest poses and one-to-one joint mappings."""

from __future__ import annotations

from typing import Tuple

from maya import cmds
from maya.api import OpenMaya as om

from rigflow.core.errors import RetargetError
from rigflow.core.logging import get_logger
from rigflow.scene.rest_pose import rest_pose

from .base import Retargeter, RetargetRequest, RetargetResult, chunked, sample_frames, skeleton_joints
from .baker import create_override_layer, euler_filter

log = get_logger(__name__)


def _rotation(joint: str) -> om.MMatrix:
    """World rotation stripped of translation and scale."""
    matrix = om.MMatrix(cmds.xform(joint, query=True, worldSpace=True, matrix=True))
    return om.MTransformationMatrix(matrix).rotation(asQuaternion=True).asMatrix()


class MatrixRetargeter(Retargeter):
    """Per-frame world rotation transfer. Prepare captures stance, not live preview."""

    name = "matrix"

    @classmethod
    def availability(cls) -> Tuple[bool, str]:
        """The fallback requires only Maya's built-in matrix API."""
        return True, "Matrix fallback; no live preview, IK, contacts or twist distribution"

    @chunked("RigFlow: prepare {} transfer")
    def prepare(self, request: RetargetRequest) -> None:
        """Capture source/destination world rest rotations without live preview."""
        self._begin(request)
        try:
            self._pairs = sorted(request.mapping.complete_pairs(),
                                 key=lambda p: cmds.ls(p[2], long=True)[0].count("|"))
            stance = request.stance_time if request.stance_time is not None else request.frame_range[0]
            self._source_hips, self._destination_hips = next(
                (s, d) for r, s, d in self._pairs if r == "Hips")
            with rest_pose(skeleton_joints(request.source_root), stance) as method:
                self._source_rest = {r: _rotation(s) for r, s, _ in self._pairs}
                self._source_position = cmds.xform(self._source_hips, query=True,
                                                  worldSpace=True, translation=True)
                self._warnings.append("Source stance: " + method)
            with rest_pose(skeleton_joints(request.destination_root), stance) as method:
                self._destination_rest = {r: _rotation(d) for r, _, d in self._pairs}
                self._destination_position = cmds.xform(self._destination_hips, query=True,
                                                       worldSpace=True, translation=True)
                self._warnings.append("Destination stance: " + method)
            up = "xyz".index(cmds.upAxis(query=True, axis=True))
            height = self._source_position[up]
            if abs(height) < 1e-8:
                raise RetargetError("Source hips height is zero along the scene up axis",
                                    hint="place the stance above the scene ground plane")
            self._ratio = self._destination_position[up] / height
            self._warnings.append(self.availability()[1])
            for _, source, destination in self._pairs:
                for joint in (source, destination):
                    if any(abs(v) > 1e-8 for v in cmds.getAttr(joint + ".rotateAxis")[0]):
                        self._warnings.append("Non-zero rotateAxis is not supported: " + joint)
            self._prepared = True
            log.info("Matrix stance prepared; hips height ratio %.6f", self._ratio)
        except Exception as exc:
            self.cleanup()
            if isinstance(exc, RetargetError):
                raise
            raise RetargetError("Matrix preparation failed: " + str(exc),
                                hint="check the mapping and compatible rest poses") from exc

    @chunked("RigFlow: transfer animation ({})")
    def bake(self) -> RetargetResult:
        """Key rest-frame deltas in parent order, respecting jointOrient/order."""
        request = self._require_prepared()
        previous = cmds.currentTime(query=True)
        before = set(cmds.ls() or [])
        layer = None
        try:
            layer = create_override_layer(request.layer_name) if request.bake_to_layer else None
            if layer:
                for other in cmds.ls(type="animLayer") or []:
                    cmds.animLayer(other, edit=True, selected=False, preferred=False)
                cmds.animLayer(layer, edit=True, selected=True, preferred=True)
                # Matrix keys need explicit membership; unlike HIK there is no
                # live solver to be obscured by the initial override pose.
                for _, _, joint in self._pairs:
                    for attr in ("rx", "ry", "rz"):
                        cmds.animLayer(layer, edit=True, attribute=joint + "." + attr)
                if request.transfer_root_motion:
                    for attr in ("tx", "ty", "tz"):
                        cmds.animLayer(layer, edit=True, attribute=self._destination_hips + "." + attr)
            options = {"animLayer": layer} if layer else {}
            for frame in sample_frames(request.frame_range, request.sample_by):
                cmds.currentTime(frame, edit=True)
                for role, source, joint in self._pairs:
                    source_rest = self._source_rest[role]
                    destination_rest = self._destination_rest[role]
                    delta = source_rest.inverse() * _rotation(source)
                    reexpressed = destination_rest * delta * destination_rest.inverse()
                    desired = reexpressed * destination_rest
                    parents = cmds.listRelatives(joint, parent=True, fullPath=True) or []
                    parent_rotation = _rotation(parents[0]) if parents else om.MMatrix()
                    orient = om.MEulerRotation(*[
                        om.MAngle(v, om.MAngle.uiUnit()).asRadians()
                        for v in cmds.getAttr(joint + ".jointOrient")[0]
                    ]).asMatrix()
                    local = desired * parent_rotation.inverse() * orient.inverse()
                    euler = om.MTransformationMatrix(local).rotation()
                    euler.reorderIt(cmds.getAttr(joint + ".rotateOrder"))
                    for attr, value in zip(("rx", "ry", "rz"), (euler.x, euler.y, euler.z)):
                        angle = om.MAngle(value).asUnits(om.MAngle.uiUnit())
                        cmds.setKeyframe(joint, attribute=attr, time=frame, value=angle, **options)
                    cmds.dgdirty(joint)
                    if role == "Hips" and request.transfer_root_motion:
                        position = cmds.xform(source, query=True, worldSpace=True, translation=True)
                        world = [d + self._ratio * (s - s0) for d, s, s0 in zip(
                            self._destination_position, position, self._source_position)]
                        # xform returns UI units; OpenMaya matrices/points use cm.
                        factor = om.MDistance(1, om.MDistance.uiUnit()).asCentimeters()
                        point = om.MPoint(*(v * factor for v in world))
                        if parents:
                            selection = om.MSelectionList()
                            selection.add(parents[0])
                            point *= selection.getDagPath(0).inclusiveMatrixInverse()
                        for attr, value in zip(("tx", "ty", "tz"), (point.x, point.y, point.z)):
                            cmds.setKeyframe(joint, attribute=attr, time=frame,
                                             value=value / factor, **options)
                        cmds.dgdirty(joint)
            joints = [d for _, _, d in self._pairs]
            euler_filter(joints, layer=layer, frame_range=request.frame_range)
            return self._result(layer)
        except Exception as exc:
            if isinstance(exc, RetargetError):
                raise
            raise RetargetError("Matrix bake failed: " + str(exc),
                                hint="check writable channels and compatible joint transforms") from exc
        finally:
            self._record_nodes(before)
            cmds.currentTime(previous, edit=True)
            self.cleanup()
