"""Exercise existing rest-pose helpers against real bind poses and animation."""

from __future__ import annotations

import unittest

from maya import cmds

import scene_fixtures as sf
import fixtures
from rigflow.scene.rest_pose import rest_pose
from rigflow.scene.undo import undo_chunk


class RestPoseTests(unittest.TestCase):
    def setUp(self):
        sf.new_scene()

    def _check_restores(self, created, roles, expected_method):
        sf.animate_jump(created, roles)
        joints = list(created.values())
        hips = created[roles["Hips"]]
        cmds.currentTime(24)
        before = sf.sample(joints, [24])
        keys = cmds.keyframe(query=True, keyframeCount=True)
        with undo_chunk("test rest pose"):
            with rest_pose(joints, stance_time=1) as method:
                self.assertTrue(method.startswith(expected_method), method)
                self.assertAlmostEqual(cmds.xform(hips, query=True, worldSpace=True,
                                                 translation=True)[1],
                                       66 if expected_method.startswith("dagPose") else 100, delta=1e-4)
        self.assertEqual(cmds.currentTime(query=True), 24)
        after = sf.sample(joints, [24])
        for joint in joints:
            for actual, expected in zip(after[joint][0], before[joint][0]):
                self.assertAlmostEqual(actual, expected, delta=1e-4)
        self.assertEqual(cmds.keyframe(query=True, keyframeCount=True), keys)

    def test_bind_pose_restoration(self):
        created = sf.build_skeleton(fixtures.custom_spec())
        cube = cmds.polyCube()[0]
        cmds.skinCluster([created["pelvis_JNT"], created["chest_JNT"]], cube, toSelectedBones=True)
        self._check_restores(created, sf.custom_roles(), "dagPose:")

    def test_zero_rotation_fallback(self):
        self._check_restores(sf.build_skeleton(fixtures.mixamo_spec()), sf.mixamo_roles(), "zero-rotation")

    def test_body_exception_restores_pose(self):
        created = sf.build_skeleton(fixtures.mixamo_spec())
        sf.animate_jump(created, sf.mixamo_roles())
        cmds.currentTime(24)
        root = created["mixamorig:Hips"]
        before = cmds.xform(root, query=True, worldSpace=True, translation=True)
        with self.assertRaisesRegex(RuntimeError, "body failure"):
            with undo_chunk("exception restoration"):
                with rest_pose(created.values(), stance_time=1):
                    raise RuntimeError("body failure")
        self.assertEqual(cmds.currentTime(query=True), 24)
        self.assertEqual(cmds.xform(root, query=True, worldSpace=True, translation=True), before)
