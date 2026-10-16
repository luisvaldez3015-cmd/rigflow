"""HumanIK live preview, bake fidelity, animation layers and undo."""

from __future__ import annotations

import unittest

from maya import cmds

from rigflow.retargeting import HumanIKRetargeter
from rigflow.retargeting.verify import sample_world_positions
from rigflow.scene.undo import undo_chunk
from test_retarget_common import RetargetFixture


class TestHumanIKRetargeter(RetargetFixture, unittest.TestCase):
    def test_cancel_restores_original_scene_and_animation(self):
        self.existing_destination_keys()
        before = sample_world_positions(self.destination_joints(), [1, 24, 48])
        nodes = set(cmds.ls())
        backend = self.backend(HumanIKRetargeter)
        backend.prepare(self.request)
        backend.cleanup()
        self.assertEqual(set(cmds.ls()), nodes)
        after = sample_world_positions(self.destination_joints(), [1, 24, 48])
        for joint in before:
            for p, q in zip(before[joint], after[joint]):
                for a, b in zip(p, q):
                    self.assertAlmostEqual(a, b, places=5)

    def test_no_root_motion_and_only_mapped_channels_baked(self):
        self.request.transfer_root_motion = False
        self.request.bake_to_layer = False
        backend = self.backend(HumanIKRetargeter)
        backend.prepare(self.request)
        backend.bake()
        points = sample_world_positions(["pelvis_JNT"], [1, 24, 48])["pelvis_JNT"]
        self.assertEqual(points[0], points[1])
        self.assertEqual(points[0], points[2])
        for joint in self.destination_joints():
            self.assertFalse(cmds.keyframe(joint, attribute=["tx", "ty", "tz"],
                                          query=True, keyframeCount=True))
        self.assertFalse(cmds.keyframe("root_JNT", query=True, keyframeCount=True))

    def test_live_preview_and_direct_bake(self):
        self.request.bake_to_layer = False
        backend = self.backend(HumanIKRetargeter)
        source_curves = self.source_curves()
        backend.prepare(self.request)
        self.assertTrue(backend.prepared)
        joints = self.destination_joints()
        self.assertFalse(any(cmds.keyframe(j, query=True, keyframeCount=True) for j in joints))
        before = sample_world_positions(joints, range(1, 49))
        hips = before["pelvis_JNT"]
        self.assertGreater(hips[23][1] - hips[0][1], 45 * 0.4)
        self.assertLess(hips[23][1] - hips[0][1], 45)
        self.assertNotEqual(before["l_wrist_JNT"][0], before["l_wrist_JNT"][23])
        result = backend.bake()
        self.assertFalse(backend.prepared)
        self.assertIsNone(result.layer)
        for joint in joints:
            for attribute in ("rx", "ry", "rz"):
                self.assertEqual(cmds.keyframe(joint, attribute=attribute,
                                              query=True, keyframeCount=True), 48)
        for attribute in ("tx", "ty", "tz"):
            self.assertEqual(cmds.keyframe("pelvis_JNT", attribute=attribute,
                                          query=True, keyframeCount=True), 48)
        after = sample_world_positions(joints, range(1, 49))
        error = max(abs(a - b) for joint in joints for p, q in zip(before[joint], after[joint])
                    for a, b in zip(p, q))
        self.assertLess(error, 1e-3)
        self.assertFalse(cmds.ls(type="HIKCharacterNode"))
        self.assertEqual(source_curves, self.source_curves())
        self.report_motion(backend, result)

    def test_layer_preserves_existing_destination_animation(self):
        self.assert_preserved_layer(HumanIKRetargeter)

    def test_single_undo_restores_rest_pose(self):
        cmds.undoInfo(state=True, infinity=True)
        before = sample_world_positions(self.destination_joints(), [1, 24, 48])
        backend = self.backend(HumanIKRetargeter)
        # Same shape as the UI controller: prepare + bake inside one outer chunk.
        with undo_chunk("RigFlow: transfer (test)"):
            backend.prepare(self.request)
            result = backend.bake()
        cmds.undo()
        self.assertFalse(cmds.objExists(result.layer))
        self.assertFalse(cmds.ls(type="HIKCharacterNode"))
        for joint in self.destination_joints():
            self.assertFalse(cmds.keyframe(joint, query=True, keyframeCount=True))
        after = sample_world_positions(self.destination_joints(), [1, 24, 48])
        for joint in before:
            for p, q in zip(before[joint], after[joint]):
                for a, b in zip(p, q):
                    self.assertAlmostEqual(a, b, places=5)

    def test_partial_optional_mapping(self):
        for role in ("LeftToeBase", "RightToeBase", "Neck"):
            self.mapping.matches.pop(role)
        backend = self.backend(HumanIKRetargeter)
        backend.prepare(self.request)
        result = backend.bake()
        self.report_motion(backend, result)
        for joint in ("l_ball_JNT", "r_ball_JNT", "neck_JNT"):
            self.assertFalse(cmds.keyframe(joint, query=True, keyframeCount=True))
