"""Real Maya inspection and animation graph coverage."""

from __future__ import annotations

import unittest

from maya import cmds

import scene_fixtures as sf
import fixtures
from rigflow.scene import (
    animation_range, find_meshes, find_skeleton_roots, has_animation, inspect_scene,
    is_control, scene_fps, selection, set_playback_range, skeleton_root_for_mesh,
)


class SceneInspectorTests(unittest.TestCase):
    def setUp(self):
        sf.new_scene()

    def test_content_and_restricted_scope(self):
        mixamo = sf.build_skeleton(fixtures.mixamo_spec())
        custom = sf.build_skeleton(fixtures.custom_spec())
        cube = cmds.polyCube(name="body")[0]
        cluster = cmds.skinCluster([custom["pelvis_JNT"], custom["chest_JNT"]], cube,
                                   toSelectedBones=True)[0]
        sphere = cmds.polySphere(name="prop")[0]
        cmds.circle(name="arm_CTRL")
        self.assertEqual(set(find_skeleton_roots()), {mixamo["mixamorig:Hips"], custom["root_JNT"]})
        meshes = {mesh.transform: mesh for mesh in find_meshes()}
        self.assertTrue(meshes[cube].skinned)
        self.assertEqual(meshes[cube].skin_cluster, cluster)
        self.assertIn(custom["pelvis_JNT"], meshes[cube].influences)
        self.assertEqual(meshes[cube].vertex_count, 8)
        self.assertFalse(meshes[sphere].skinned)
        self.assertIsNone(meshes[sphere].skin_cluster)
        self.assertEqual(skeleton_root_for_mesh(meshes[cube]), custom["root_JNT"])
        self.assertIsNone(skeleton_root_for_mesh(meshes[sphere]))
        self.assertTrue(is_control("arm_CTRL"))
        report = inspect_scene()
        self.assertTrue(report.has_skeleton)
        self.assertTrue(report.has_mesh)
        self.assertFalse(report.has_animation)
        self.assertIsNone(report.frame_range)
        self.assertEqual((report.fps, report.linear_unit, report.up_axis), (24, "cm", "y"))
        self.assertTrue(report.describe())
        sf.animate_jump(mixamo, sf.mixamo_roles())
        self.assertEqual(inspect_scene().frame_range, (1, 48))
        restricted = inspect_scene([custom["root_JNT"]])
        self.assertEqual([s.root for s in restricted.skeletons], [custom["root_JNT"]])
        self.assertIsNone(restricted.frame_range)
        self.assertTrue(restricted.skeletons[0].has_bind_pose)

    def test_empty_dg_selection_and_helpers(self):
        dg = cmds.createNode("multiplyDivide", name="calculation")
        cmds.select(dg)
        self.assertEqual(selection(), [dg])
        self.assertFalse(is_control(dg))
        self.assertFalse(inspect_scene([dg]).has_skeleton)
        self.assertFalse(inspect_scene([]).has_mesh)
        self.assertIsNone(animation_range([dg, "missing"]))
        group = cmds.group(empty=True, name="rigflow_hik_helpers")
        cmds.select(clear=True)
        joint = cmds.joint(name="helperRoot")
        cmds.parent(joint, group)
        self.assertEqual(find_skeleton_roots(), [])
        self.assertFalse(inspect_scene().has_animation)

    def test_duplicate_names_and_joint_ancestors_across_transforms(self):
        root = cmds.joint(name="root")
        group = cmds.createNode("transform", name="between", parent=root)
        child = cmds.createNode("joint", name="child", parent=group)
        other = cmds.group(empty=True, name="other")
        cmds.createNode("joint", name="child", parent=other)
        self.assertEqual(set(find_skeleton_roots()), {root, "|other|child"})
        self.assertEqual(find_skeleton_roots(["|root|between|child"]), [])
        self.assertEqual(set(inspect_scene([root]).skeletons[0].joints), {root, "|root|between|child"})

    def test_pairblend_layers_and_scene_units(self):
        root = cmds.joint(name="root")
        child = cmds.joint(name="child")
        curve = cmds.createNode("animCurveTL")
        cmds.setKeyframe(curve, time=-5, value=0)
        cmds.setKeyframe(curve, time=80, value=10)
        blend = cmds.createNode("pairBlend")
        cmds.connectAttr(curve + ".output", blend + ".inTranslateX1")
        cmds.connectAttr(blend + ".outTranslateX", child + ".translateX")
        self.assertTrue(has_animation(child))
        self.assertFalse(has_animation(root))
        self.assertEqual(animation_range([root]), (-5, 80))
        cmds.select(root)
        layer = cmds.animLayer("motion", addSelectedObjects=True)
        cmds.setKeyframe(root, attribute="rotateY", time=2, value=0, animLayer=layer)
        cmds.setKeyframe(root, attribute="rotateY", time=90, value=20, animLayer=layer)
        self.assertTrue(has_animation(root))
        self.assertEqual(animation_range([root]), (-5, 90))
        for unit, fps in (("game", 15), ("film", 24), ("pal", 25), ("ntsc", 30),
                          ("show", 48), ("palf", 50), ("ntscf", 60), ("23.976fps", 23.976)):
            cmds.currentUnit(time=unit)
            self.assertAlmostEqual(scene_fps(), fps)
        cmds.currentUnit(linear="m")
        cmds.upAxis(axis="z", rotateView=False)
        report = inspect_scene([root])
        self.assertEqual((report.linear_unit, report.up_axis), ("m", "z"))
        set_playback_range(3, 27)
        for flag, expected in (("minTime", 3), ("maxTime", 27),
                               ("animationStartTime", 3), ("animationEndTime", 27)):
            self.assertEqual(cmds.playbackOptions(query=True, **{flag: True}), expected)
