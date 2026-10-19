"""Model detection across DAG selection scopes and skin connections."""

from __future__ import annotations

import os
import unittest

from maya import cmds

import scene_fixtures as sf
from rigflow.scene import (CharacterScan, ImportResult, inspect_scene, meshes_for_skeleton,
                           scan_import, scan_nodes)
from rigflow.scene.demo import build_demo_scene


class SceneCharactersTests(unittest.TestCase):
    def setUp(self):
        sf.new_scene()
        self.demo = build_demo_scene()

    def tearDown(self):
        sf.new_scene()

    def test_animated_source_root_only(self):
        scan = scan_nodes([self.demo.source_root], "Source")
        self.assertIsInstance(scan, CharacterScan)
        self.assertEqual(scan.name, "Source")
        self.assertTrue(scan.has_rig)
        self.assertTrue(scan.has_anim)
        self.assertFalse(scan.has_mesh)
        self.assertEqual(scan.frame_range, (1, 48))
        self.assertEqual(scan.fps, 24)
        self.assertEqual(scan.skeleton.root, self.demo.source_root)
        self.assertEqual(scan.other_roots, [])

    def test_mesh_only_selection_follows_skin_influences(self):
        scan = scan_nodes([self.demo.destination_mesh], "Destination")
        self.assertTrue(scan.has_mesh)
        self.assertTrue(scan.meshes[0].skinned)
        self.assertTrue(scan.has_rig)
        self.assertEqual(scan.skeleton.root, self.demo.destination_root)
        self.assertTrue(scan.warnings)
        self.assertIn("influences", scan.warnings[0])
        self.assertFalse(scan.has_anim)
        self.assertIsNone(scan.frame_range)

    def test_root_only_selection_finds_skinned_mesh(self):
        linked = meshes_for_skeleton(self.demo.destination_root)
        self.assertEqual([m.transform for m in linked], [self.demo.destination_mesh])
        scan = scan_nodes([self.demo.destination_root], "Destination")
        self.assertEqual([m.transform for m in scan.meshes], [self.demo.destination_mesh])
        self.assertTrue(scan.has_rig)
        self.assertFalse(scan.has_anim)

    def test_whole_scene_prefers_mesh_skeleton_over_larger_animated_rig(self):
        scan = scan_nodes(None, "Scene")
        self.assertEqual(scan.skeleton.root, self.demo.destination_root)
        self.assertEqual(scan.other_roots, [self.demo.source_root])
        self.assertFalse(scan.has_anim)
        self.assertIsNone(scan.frame_range)
        # Without skinned geometry the larger joint hierarchy wins.
        cmds.delete(self.demo.destination_mesh)
        scan = scan_nodes(None, "Scene")
        self.assertEqual(scan.skeleton.root, self.demo.source_root)
        self.assertEqual(scan.other_roots, [self.demo.destination_root])

    def test_unskinned_mesh_and_mesh_keys_do_not_imply_rig_animation(self):
        sf.new_scene()
        mesh = cmds.polyCube()[0]
        cmds.setKeyframe(mesh, attribute="translateX", time=1, value=0)
        cmds.setKeyframe(mesh, attribute="translateX", time=80, value=5)
        scan = scan_nodes(None, "Prop")
        self.assertTrue(scan.has_mesh)
        self.assertFalse(scan.meshes[0].skinned)
        self.assertFalse(scan.has_rig)
        self.assertFalse(scan.has_anim)
        self.assertIsNone(scan.frame_range)

    def test_helpers_empty_scope_and_import_name(self):
        group = cmds.group(empty=True, name="rigflow_helpers")
        joint = cmds.createNode("joint", name="helperJoint", parent=group)
        cube = cmds.polyCube()[0]
        cmds.parent(cube, group)
        cmds.setKeyframe(joint, attribute="translateY", time=100, value=2)
        scan = scan_nodes(None, "Scene")
        self.assertEqual(scan.other_roots, [self.demo.source_root])
        self.assertEqual([m.transform for m in scan.meshes], [self.demo.destination_mesh])
        self.assertFalse(scan_nodes([group], "Helpers").has_rig)
        empty = scan_nodes([], "Empty")
        self.assertFalse(empty.has_mesh or empty.has_rig or empty.has_anim)
        nodes = [self.demo.source_root]
        result = ImportResult(os.path.join("models", "walk cycle.fbx"), "fbx", "mixamorig",
                              nodes, inspect_scene(nodes))
        imported = scan_import(result)
        self.assertEqual(imported.name, "walk cycle")
        self.assertTrue(imported.has_anim)

    def test_descendant_controls_and_helpers_do_not_extend_joint_animation(self):
        group = cmds.createNode("transform", name="rigflow_helpers", parent=self.demo.destination_root)
        joint = cmds.createNode("joint", name="helperJoint", parent=group)
        cmds.setKeyframe(joint, attribute="translateY", time=100, value=2)
        cmds.setKeyframe(self.demo.facial_controls[0], attribute="translateX", time=120, value=3)
        scan = scan_nodes(None, "Scene")
        self.assertIsNone(scan.frame_range)
        self.assertFalse(scan.has_anim)
        self.assertNotIn(joint, scan.skeleton.joints)
        source_helper = cmds.createNode("transform", name="rigflow_source_helper", parent=self.demo.source_root)
        cmds.setKeyframe(source_helper, attribute="translateY", time=200, value=2)
        source = scan_nodes([self.demo.source_root], "Source")
        self.assertEqual(source.frame_range, (1, 48))
