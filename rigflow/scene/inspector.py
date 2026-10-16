"""Describe usable scene content without assuming meshes are rigs or joints animate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from maya import cmds

from rigflow.core.logging import get_logger
from rigflow.scene import animation_io
from rigflow.scene.rest_pose import bind_pose_node
from rigflow.skeleton.naming import IGNORE_TOKENS
from rigflow.utils.strings import namespace_of, short_name, split_tokens

log = get_logger(__name__)
_CONTROL_TOKENS = dict(IGNORE_TOKENS)["control"]


def _unique_name(node: str) -> str:
    """Use the leaf name when unique, otherwise the complete DAG path."""
    leaf = node.rsplit("|", 1)[-1]
    matches = cmds.ls(leaf, long=True) or []
    return leaf if len(matches) == 1 else (cmds.ls(node, long=True) or [node])[0]


def _is_helper(node: str) -> bool:
    """Exclude internal helper ancestry, while retaining source import namespaces."""
    parts = node.split("|")
    for i, part in enumerate(parts):
        if not part:
            continue
        if "rigflow_" in short_name(part).lower():
            return True
        ancestor = "|".join(parts[:i + 1])
        if cmds.nodeType(ancestor).lower().startswith("hik"):
            return True
    return False


def _scene_nodes(nodes: Optional[Sequence[str]]) -> List[str]:
    candidates = (cmds.ls(long=True) or []) if nodes is None else animation_io._expanded_nodes(nodes)
    return [n for n in candidates if not _is_helper(n)]


def _joint_ancestor(node: str) -> Optional[str]:
    """Return the nearest joint ancestor, crossing ordinary transform groups."""
    parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
    while parents:
        parent = parents[0]
        if cmds.nodeType(parent) == "joint":
            return parent
        parents = cmds.listRelatives(parent, parent=True, fullPath=True) or []
    return None


@dataclass
class MeshInfo:
    """A non-intermediate polygon shape and its skin influences."""

    transform: str
    shape: str
    vertex_count: int
    skinned: bool
    skin_cluster: Optional[str]
    influences: List[str]


@dataclass
class SkeletonInfo:
    """Joint hierarchy metadata from the current scene."""

    root: str
    joints: List[str]
    animated_joints: int
    has_bind_pose: bool
    namespace: str

    @property
    def joint_count(self) -> int:
        """Number of joints in this hierarchy."""
        return len(self.joints)


@dataclass
class SceneReport:
    """Actual mesh, skeleton, control and animation content of a scene scope."""

    meshes: List[MeshInfo]
    skeletons: List[SkeletonInfo]
    controls: List[str]
    frame_range: Optional[Tuple[float, float]]
    fps: float
    time_unit: str
    linear_unit: str
    up_axis: str
    warnings: List[str]

    @property
    def has_animation(self) -> bool:
        """Whether any keys were found in the inspected scope."""
        return self.frame_range is not None

    @property
    def has_mesh(self) -> bool:
        """Whether polygon meshes were found."""
        return bool(self.meshes)

    @property
    def has_skeleton(self) -> bool:
        """Whether joint hierarchies were found."""
        return bool(self.skeletons)

    def describe(self) -> str:
        """Short multiline summary suitable for the scene inspection UI."""
        animation = ("Keys: {:g}-{:g}".format(*self.frame_range)
                     if self.frame_range is not None else "No animation keys found")
        lines = ["{} skeletons ({} joints), {} meshes ({} skinned), {} controls".format(
            len(self.skeletons), sum(s.joint_count for s in self.skeletons), len(self.meshes),
            sum(m.skinned for m in self.meshes), len(self.controls)), animation,
            "{:g} fps | {} | {} up".format(self.fps, self.linear_unit, self.up_axis.upper())]
        return "\n".join(lines + self.warnings)


def find_skeleton_roots(nodes: Optional[Sequence[str]] = None) -> List[str]:
    """Find globally top-most joints within nodes and descendants."""
    return sorted(_unique_name(n) for n in _scene_nodes(nodes)
                  if cmds.nodeType(n) == "joint" and _joint_ancestor(n) is None)


def find_meshes(nodes: Optional[Sequence[str]] = None) -> List[MeshInfo]:
    """Find polygon meshes, excluding intermediate shapes and internal helpers."""
    result = []
    for shape in _scene_nodes(nodes):
        if cmds.nodeType(shape) != "mesh" or cmds.getAttr(shape + ".intermediateObject"):
            continue
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        if not parents:
            continue
        history = cmds.listHistory(shape, pruneDagObjects=True) or []
        clusters = cmds.ls(history, type="skinCluster") if history else []
        cluster = clusters[0] if clusters else None
        influences = cmds.skinCluster(cluster, query=True, influence=True) if cluster else []
        result.append(MeshInfo(_unique_name(parents[0]), _unique_name(shape),
                               int(cmds.polyEvaluate(shape, vertex=True)), bool(cluster),
                               cluster, [_unique_name(j) for j in influences or []]))
    return sorted(result, key=lambda mesh: mesh.shape)


def is_control(node: str) -> bool:
    """Recognize transform controls using shapes or the shared naming vocabulary."""
    if not cmds.objExists(node) or cmds.nodeType(node) != "transform":
        return False
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True) or []
    return (any(cmds.nodeType(s) in ("nurbsCurve", "locator") for s in shapes)
            or bool(set(split_tokens(node)) & _CONTROL_TOKENS))


def skeleton_root_for_mesh(mesh: MeshInfo) -> Optional[str]:
    """Return a top-most joint reached through the mesh's skin influences."""
    roots = set()
    for influence in mesh.influences:
        if not cmds.objExists(influence) or cmds.nodeType(influence) != "joint":
            continue
        root = influence
        parent = _joint_ancestor(root)
        while parent:
            root, parent = parent, _joint_ancestor(parent)
        roots.add(_unique_name(root))
    return sorted(roots)[0] if roots else None


def selection() -> List[str]:
    """Return unique selected object names, including non-DAG nodes."""
    return list(dict.fromkeys(_unique_name(n) for n in
                             cmds.ls(selection=True, long=True, objectsOnly=True) or []))


def inspect_scene(nodes: Optional[Sequence[str]] = None) -> SceneReport:
    """Inspect the whole scene or only given nodes and their descendants."""
    scope = _scene_nodes(nodes)
    skeletons = []
    for root in find_skeleton_roots(scope):
        joints = [_unique_name(j) for j in _scene_nodes([root]) if cmds.nodeType(j) == "joint"]
        skeletons.append(SkeletonInfo(root, joints, sum(animation_io.has_animation(j) for j in joints),
                                     bind_pose_node(joints) is not None, namespace_of(root)))
    meshes = find_meshes(scope)
    controls = sorted(_unique_name(n) for n in scope if is_control(n))
    # Scope is already expanded and filtered; do not reintroduce helper descendants.
    curves = animation_io._animation_curves(scope)
    times = cmds.keyframe(curves, query=True, timeChange=True) if curves else []
    frame_range = (float(min(times)), float(max(times))) if times else None
    return SceneReport(meshes, skeletons, controls, frame_range, animation_io.scene_fps(),
                       animation_io.time_unit(), animation_io.linear_unit(), animation_io.up_axis(), [])
