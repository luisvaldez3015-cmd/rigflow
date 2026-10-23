"""Copy a rest skeleton, fit its height and position, then optionally bind skin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from maya import cmds
from maya.api import OpenMaya as om

from rigflow.core.errors import SceneError
from rigflow.core.logging import get_logger
from rigflow.scene.animation_io import up_axis
from rigflow.scene.inspector import MeshInfo, _unique_name, find_meshes
from rigflow.scene.rest_pose import rest_pose
from rigflow.scene.skeleton_reader import _joints
from rigflow.scene.undo import undo_chunk
from rigflow.scene.characters import meshes_for_skeleton
from rigflow.scene.similarity import (dag_path, skin_function, vertex_component,
                                      meshes_at_rest, surfaces, same_topology)

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
                source_meshes = [m for m in meshes_for_skeleton(source_root) if m.skinned]
                source_bounds = _visible_bounds(source_meshes) if source_meshes else None
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
            bounds = source_bounds or _joint_bounds(joints)
            joint_height = bounds[axis + 3] - bounds[axis]
            if joint_height <= 1e-10:
                raise SceneError("Skeleton height is zero", hint="Choose a skeleton with nonzero height along the scene up axis.")
            scale = mesh_height / joint_height
            for joint in joints:
                translate = cmds.getAttr(joint + ".translate")[0]
                cmds.setAttr(joint + ".translate", *(v * scale for v in translate))
                cmds.setAttr(joint + ".radius", cmds.getAttr(joint + ".radius") * scale)
            bounds = [v * scale for v in source_bounds] if source_bounds else _joint_bounds(joints)
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
    """Copy source skin weights by index or closest normalised surface triangle.

    Different shapes receive a starting point to polish by hand. Weights are
    written with undoable ``setAttr`` calls, so undo and redo need no plug-in.
    """
    with undo_chunk("RigFlow: bind rig"):
        meshes = _mesh_transforms(meshes)
        clusters = []
        try:
            source_meshes = [m.transform for m in meshes_for_skeleton(fit.source_joints[0]) if m.skinned]
            if not source_meshes:
                raise SceneError("Source rig has no skinned mesh", hint="Choose a source mesh with skin weights to copy.")
            with meshes_at_rest(source_meshes):
                source, _ = surfaces(source_meshes)
                target, _ = surfaces(meshes)
                source_weights = []
                for surface in source:
                    skin = skin_function(surface.info.skin_cluster)
                    weights, count = skin.getWeights(dag_path(surface.info.shape), vertex_component(len(surface.points)))
                    source_weights.append((weights, count, [p.fullPathName() for p in skin.influenceObjects()]))
            joint_map = {dag_path(s).fullPathName(): dag_path(d).fullPathName()
                         for s, d in zip(fit.source_joints, fit.joints)}
            for mesh in meshes:
                cluster = cmds.skinCluster(fit.joints, mesh, toSelectedBones=True, bindMethod=0,
                                           normalizeWeights=1, maximumInfluences=max_influences,
                                           obeyMaxInfluences=False, dropoffRate=4.0,
                                           name="rigflow_skin#")[0]
                clusters.append(cluster)
                skin = skin_function(cluster)
                influences = {p.fullPathName(): i for i, p in enumerate(skin.influenceObjects())}
                for destination in [s for s in target if s.info.transform == mesh]:
                    compatible = [i for i, s in enumerate(source) if same_topology(s, destination)]
                    direct = min(compatible, key=lambda i: sum((a - b).length()
                                 for a, b in zip(source[i].points, destination.points))) if compatible else None
                    values = om.MDoubleArray()
                    for index, point in enumerate(destination.points):
                        if direct is not None:
                            surface_index, vertices, bary = direct, [index], [1.0]
                        else:
                            candidates = [(s.fn.getClosestPoint(point, om.MSpace.kObject), i) for i, s in enumerate(source)]
                            (closest, face), surface_index = min(candidates, key=lambda c: (c[0][0] - point).length())
                            vertices, bary = _triangle_weights(source[surface_index], closest, face)
                        weights, count, source_joints = source_weights[surface_index]
                        row = [0.0] * len(influences)
                        for j, source_joint in enumerate(source_joints):
                            fitted_joint = joint_map.get(source_joint)
                            if fitted_joint in influences:
                                row[influences[fitted_joint]] += sum(weights[v * count + j] * factor
                                                                    for v, factor in zip(vertices, bary))
                        total = sum(row)
                        if total < 1e-12:
                            raise SceneError("Source weights do not belong to the copied skeleton",
                                             hint="Choose the skeleton influencing the source mesh.")
                        for value in row:
                            values.append(value / total)
                    logical = [skin.indexForInfluenceObject(p) for p in skin.influenceObjects()]
                    _write_weights(cluster, list(values), logical)
        except Exception as exc:
            if clusters:
                cmds.delete(clusters)
            if isinstance(exc, SceneError):
                raise
            raise SceneError("Could not bind fitted skeleton: {}".format(exc),
                             hint="Keep the fitted joints in the scene and choose unskinned meshes.") from exc
        fit.skin_clusters.extend(clusters)
        log.info("Bound %d meshes to %s", len(clusters), fit.root)
        return fit


def _write_weights(cluster: str, values: List[float], logical: List[int]) -> None:
    """Write one weight row per vertex with plain ``setAttr`` calls.

    Maya records each call in the open undo chunk, so undo and redo restore the
    copied weights without loading a plug-in (about 1 s for 20k vertices).
    """
    count = len(logical)
    contiguous = logical == list(range(logical[0], logical[0] + count)) if count else False
    previous = cmds.getAttr(cluster + ".normalizeWeights")
    cmds.setAttr(cluster + ".normalizeWeights", 0)
    try:
        for vertex in range(len(values) // count):
            row = values[vertex * count:(vertex + 1) * count]
            plug = "{}.weightList[{}].weights".format(cluster, vertex)
            if contiguous:
                cmds.setAttr("{}[{}:{}]".format(plug, logical[0], logical[-1]), *row, size=count)
            else:
                for index, value in zip(logical, row):
                    cmds.setAttr("{}[{}]".format(plug, index), value)
    finally:
        cmds.setAttr(cluster + ".normalizeWeights", previous)


def _triangle_weights(surface, point, face):
    """Barycentric weights at the closest point on a triangulated polygon."""
    triangle_counts, vertices = surface.triangles
    start = sum(triangle_counts[:face]) * 3
    best = None
    for offset in range(start, start + triangle_counts[face] * 3, 3):
        ids = list(vertices[offset:offset + 3])
        a, b, c = [surface.points[i] for i in ids]
        v0, v1, v2 = b - a, c - a, point - a
        d00, d01, d11 = v0 * v0, v0 * v1, v1 * v1
        denominator = d00 * d11 - d01 * d01
        if abs(denominator) < 1e-20:
            continue
        v = (d11 * (v2 * v0) - d01 * (v2 * v1)) / denominator
        w = (d00 * (v2 * v1) - d01 * (v2 * v0)) / denominator
        bary = [1 - v - w, v, w]
        penalty = sum(max(0, -x) for x in bary)
        if best is None or penalty < best[0]:
            best = penalty, ids, bary
    if best is None:
        ids = list(surface.fn.getPolygonVertices(face))
        return [min(ids, key=lambda i: (surface.points[i] - point).length())], [1.0]
    bary = [max(0, x) for x in best[2]]
    return best[1], [x / sum(bary) for x in bary]


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
