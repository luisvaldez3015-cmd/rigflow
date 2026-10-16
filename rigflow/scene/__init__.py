"""Maya scene access: inspection, import, skeleton reading, undo and rest-pose
helpers. Everything here imports ``maya.cmds`` and must only be used inside
Maya or after ``maya.standalone.initialize()``."""

from rigflow.scene.animation_io import (
    animation_range, has_animation, linear_unit, scene_fps, set_playback_range, time_unit, up_axis,
)
from rigflow.scene.importer import ImportResult, import_file, remove_import
from rigflow.scene.inspector import (
    MeshInfo, SceneReport, SkeletonInfo, find_meshes, find_skeleton_roots, inspect_scene,
    is_control, selection, skeleton_root_for_mesh,
)
from rigflow.scene.rest_pose import bind_pose_node, rest_pose
from rigflow.scene.skeleton_reader import read_skeleton, read_skeleton_rest
from rigflow.scene.undo import suspended_undo, undo_chunk, undoable
from rigflow.scene.viewport import create_model_panel, delete_model_panel, frame_nodes, panel_container

__all__ = [
    "MeshInfo", "SkeletonInfo", "SceneReport", "ImportResult", "inspect_scene",
    "find_skeleton_roots", "find_meshes", "is_control", "skeleton_root_for_mesh", "selection",
    "read_skeleton", "read_skeleton_rest", "import_file", "remove_import", "animation_range",
    "has_animation", "scene_fps", "time_unit", "linear_unit", "up_axis", "set_playback_range",
    "create_model_panel", "delete_model_panel", "frame_nodes", "rest_pose", "bind_pose_node",
    "undo_chunk", "undoable", "suspended_undo",
]
