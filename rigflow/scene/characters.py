"""Detect the mesh, rig and animation belonging to one Setup model."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from maya import cmds

from rigflow.core.logging import get_logger
from rigflow.scene import animation_io, inspector
from rigflow.scene.importer import ImportResult

log = get_logger(__name__)


@dataclass
class CharacterScan:
    """Usable content of a model, with animation restricted to its main rig."""

    name: str
    meshes: List[inspector.MeshInfo]
    skeleton: Optional[inspector.SkeletonInfo]
    other_roots: List[str]
    frame_range: Optional[Tuple[float, float]]
    fps: float
    warnings: List[str]

    @property
    def has_mesh(self) -> bool:
        return bool(self.meshes)

    @property
    def has_rig(self) -> bool:
        return self.skeleton is not None

    @property
    def has_anim(self) -> bool:
        return (self.frame_range is not None and self.skeleton is not None
                and self.skeleton.animated_joints > 0)


def meshes_for_skeleton(root: str) -> List[inspector.MeshInfo]:
    """Find scene meshes influenced by any non-helper joint under ``root``."""
    joints = {n for n in inspector._scene_nodes([root]) if cmds.nodeType(n) == "joint"}
    return [mesh for mesh in inspector.find_meshes()
            if mesh.influences and any(j in joints for j in cmds.ls(mesh.influences, long=True) or [])]


def scan_nodes(nodes: Optional[Sequence[str]], name: str) -> CharacterScan:
    """Scan a model, following skin connections beyond the selected DAG scope."""
    report = inspector.inspect_scene(nodes)
    skeletons = {s.root: s for s in report.skeletons}
    meshes = {m.shape: m for m in report.meshes}
    warnings = list(report.warnings)
    # Root-only selections still represent the complete skinned model.
    for root in list(skeletons):
        meshes.update((m.shape, m) for m in meshes_for_skeleton(root))
    linked_roots = []
    for mesh in sorted(meshes.values(), key=lambda m: m.shape):
        root = inspector.skeleton_root_for_mesh(mesh)
        if root is None:
            continue
        path = (cmds.ls(root, long=True) or [root])[0]
        if inspector._is_helper(path):
            continue
        if root not in skeletons:
            external = inspector.inspect_scene([root]).skeletons
            if not external:
                continue
            skeletons[root] = external[0]
            warnings.append("Skeleton {} was found outside the selection through skin influences on {}."
                            .format(root, mesh.transform))
        linked_roots.append(root)
    main = (skeletons[linked_roots[0]] if linked_roots else
            max(skeletons.values(), key=lambda s: s.joint_count, default=None))
    # animation_range expands DAG descendants. Resolve the main joints' curves
    # first so keyed controls and excluded helper descendants cannot leak in.
    curves = animation_io._animation_curves(main.joints) if main else []
    frame_range = animation_io.animation_range(curves) if curves else None
    return CharacterScan(name, sorted(meshes.values(), key=lambda m: m.shape), main,
                         sorted(r for r in skeletons if main is None or r != main.root),
                         frame_range, report.fps, warnings)


def scan_import(result: ImportResult) -> CharacterScan:
    """Scan imported content using its file stem as the model name."""
    return scan_nodes(result.new_nodes, os.path.splitext(os.path.basename(result.path))[0])
