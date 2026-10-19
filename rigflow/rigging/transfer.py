"""Copy a rest skeleton, fit its height and position, then optionally bind skin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from maya import cmds

from rigflow.core.errors import SceneError
from rigflow.core.logging import get_logger
from rigflow.scene.animation_io import up_axis
from rigflow.scene.inspector import MeshInfo, _unique_name, find_meshes
from rigflow.scene.rest_pose import rest_pose
from rigflow.scene.skeleton_reader import _joints
from rigflow.scene.undo import undo_chunk

log = get_logger(__name__)


@dataclass
class RigFitResult:
    """Owned joints and skinClusters produced by the rig-transfer services."""

    root: str
    joints: List[str]
    source_joints: List[str]
    scale: float
    offset: Tuple[float, float, float]
    skin_clusters: List[str]
    warnings: List[str]


def _polygon_meshes(meshes: Sequence[str]) -> List[MeshInfo]:
    found = find_meshes(meshes)
    if not found:
        raise SceneError("No polygon meshes to rig", hint="Choose at least one polygon mesh to fit or bind.")
    if any(m.skinned for m in found):
        raise SceneError("A mesh is already skinned", hint="Choose unskinned meshes or detach their existing skin first.")
    return found


def _mesh_transforms(meshes: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(m.transform for m in _polygon_meshes(meshes)))


def _visible_bounds(found: Sequence[MeshInfo]) -> List[float]:
    """World bounds of the rendered shapes only.

    ``exactWorldBoundingBox`` on a transform also includes intermediate
    (``*Orig``) shapes, which Maya keeps on meshes duplicated from a skinned
    character; those sit at the undeformed position and would skew the fit.
    """
    return cmds.exactWorldBoundingBox([m.shape for m in found])


def _joint_bounds(joints: Sequence[str]) -> List[float]:
    points = [cmds.xform(j, query=True, worldSpace=True, translation=True) for j in joints]
    return ([min(p[i] for p in points) for i in range(3)]
            + [max(p[i] for p in points) for i in range(3)])


def _resolve(uuid: str) -> str:
    return cmds.ls(uuid, long=True)[0]


def fit_skeleton(source_root: str, meshes: Sequence[str], namespace: Optional[str] = None,
                 stance_time: Optional[float] = None) -> RigFitResult:
    """Duplicate only rest joints and uniformly fit their bounding box to meshes."""
    with undo_chunk("RigFlow: fit rig"):
        found = _polygon_meshes(meshes)
        meshes = list(dict.fromkeys(m.transform for m in found))
        source_joints = _joints(source_root)
        axis = "xyz".index(up_axis())
        mesh_bounds = _visible_bounds(found)
        mesh_height = mesh_bounds[axis + 3] - mesh_bounds[axis]
        if mesh_height <= 1e-10:
            raise SceneError("Mesh height is zero", hint="Choose a mesh with nonzero height along the scene up axis.")
        previous_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        ns = ":" + namespace.strip(":") if namespace and namespace.strip(":") else ":"
        created_namespace = False
        duplicate_uuid = None
        try:
            cmds.namespace(setNamespace=":")
            if ns != ":" and not cmds.namespace(exists=ns):
                cmds.namespace(add=ns)
                created_namespace = True
            with rest_pose(source_joints, stance_time):
                duplicate = cmds.duplicate(source_joints[0], inputConnections=False,
                                           upstreamNodes=False, returnRootsOnly=True)[0]
                duplicate_uuid = cmds.ls(duplicate, uuid=True)[0]
                copied = _joints(duplicate)
                # Preserve joint identity through all parent and rename operations.
                copied_ids = [cmds.ls(j, uuid=True)[0] for j in copied]
                positions = {u: cmds.xform(j, query=True, worldSpace=True, translation=True)
                             for u, j in zip(copied_ids, copied)}
                reparented = False
                if cmds.listRelatives(duplicate, parent=True):
                    # Relative parenting retains the source jointOrient and rotate values.
                    cmds.parent(duplicate, world=True, relative=True)
                    reparented = True
                # Keep joints even when an ordinary transform was interposed in the source.
                for uuid in copied_ids[1:]:
                    joint = _resolve(uuid)
                    parent = cmds.listRelatives(joint, parent=True, fullPath=True)[0]
                    if cmds.nodeType(parent) != "joint":
                        ancestor = parent
                        while cmds.nodeType(ancestor) != "joint":
                            ancestor = cmds.listRelatives(ancestor, parent=True, fullPath=True)[0]
                        cmds.parent(joint, ancestor, relative=True)
                        reparented = True
                if reparented:
                    # Restore positions parent-first without letting absolute joint
                    # parenting rewrite jointOrient or insert transform parents.
                    for uuid in copied_ids:
                        cmds.xform(_resolve(uuid), worldSpace=True, translation=positions[uuid])
                descendants = cmds.listRelatives(_resolve(duplicate_uuid), allDescendents=True,
                                                 fullPath=True) or []
                for node in sorted(descendants, key=lambda n: n.count("|"), reverse=True):
                    if cmds.objExists(node) and cmds.nodeType(node) != "joint":
                        cmds.delete(node)
                cmds.cutKey([_resolve(u) for u in copied_ids], animation="objects", clear=True)
                # Children first: changing a parent name invalidates old descendant paths.
                for source, uuid in reversed(list(zip(source_joints, copied_ids))):
                    leaf = source.rsplit("|", 1)[-1].rsplit(":", 1)[-1]
                    cmds.rename(_resolve(uuid), ns.rstrip(":") + ":" + leaf)
            joints = [_unique_name(_resolve(u)) for u in copied_ids]
            root = joints[0]
            bounds = _joint_bounds(joints)
            joint_height = bounds[axis + 3] - bounds[axis]
            if joint_height <= 1e-10:
                raise SceneError("Skeleton height is zero", hint="Choose a skeleton with nonzero height along the scene up axis.")
            scale = mesh_height / joint_height
            for joint in joints:
                translate = cmds.getAttr(joint + ".translate")[0]
                cmds.setAttr(joint + ".translate", *(v * scale for v in translate))
                cmds.setAttr(joint + ".radius", cmds.getAttr(joint + ".radius") * scale)
            bounds = _joint_bounds(joints)
            offset = tuple(mesh_bounds[i] - bounds[i] if i == axis else
                           (mesh_bounds[i] + mesh_bounds[i + 3] - bounds[i] - bounds[i + 3]) / 2
                           for i in range(3))
            cmds.xform(root, relative=True, worldSpace=True, translation=offset)
            log.info("Fitted %d joints to %d meshes: scale=%g, offset=%s", len(joints), len(meshes), scale, offset)
            return RigFitResult(root, joints, [_unique_name(j) for j in source_joints],
                                scale, offset, [], [])
        except Exception as exc:
            if duplicate_uuid and cmds.ls(duplicate_uuid):
                cmds.delete(_resolve(duplicate_uuid))
            if created_namespace and cmds.namespace(exists=ns):
                cmds.namespace(removeNamespace=ns)
            if isinstance(exc, SceneError):
                raise
            raise SceneError("Could not fit skeleton: {}".format(exc),
                             hint="Choose a valid joint hierarchy and unskinned polygon meshes.") from exc
        finally:
            cmds.namespace(setNamespace=previous_namespace)


def bind_skeleton(fit: RigFitResult, meshes: Sequence[str], max_influences: int = 4) -> RigFitResult:
    """Bind each mesh to all fitted joints using closest-distance weights."""
    with undo_chunk("RigFlow: bind rig"):
        meshes = _mesh_transforms(meshes)
        clusters = []
        try:
            for mesh in meshes:
                cluster = cmds.skinCluster(fit.joints, mesh, toSelectedBones=True, bindMethod=0,
                                           normalizeWeights=1, maximumInfluences=max_influences,
                                           obeyMaxInfluences=True, dropoffRate=4.0,
                                           name="rigflow_skin#")[0]
                clusters.append(cluster)
        except Exception as exc:
            if clusters:
                cmds.delete(clusters)
            raise SceneError("Could not bind fitted skeleton: {}".format(exc),
                             hint="Keep the fitted joints in the scene and choose unskinned meshes.") from exc
        fit.skin_clusters.extend(clusters)
        log.info("Bound %d meshes to %s", len(clusters), fit.root)
        return fit


def remove_fit(fit: RigFitResult) -> None:
    """Delete only fitted joints and recorded skinClusters; repeated calls are safe."""
    with undo_chunk("RigFlow: remove rig"):
        clusters = [n for n in fit.skin_clusters if cmds.objExists(n)]
        if clusters:
            cmds.delete(clusters)
        joints = [j for j in fit.joints if cmds.objExists(j)]
        if joints:
            cmds.delete(joints)
        log.info("Removed fitted rig %s", fit.root)
