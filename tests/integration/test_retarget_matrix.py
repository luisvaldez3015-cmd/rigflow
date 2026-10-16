"""Matrix fallback across differing joint orientations, layers and scene units."""

from __future__ import annotations

import math
import unittest

from maya import cmds

from rigflow.retargeting import MatrixRetargeter
from rigflow.retargeting.verify import sample_world_positions
from rigflow.scene.undo import undo_chunk
from test_retarget_common import RetargetFixture


class TestMatrixRetargeter(RetargetFixture, unittest.TestCase):
    def test_direct_bake_motion_and_bone_lengths(self):
        self.request.bake_to_layer = False
        source = self.source_curves()
        backend = self.backend(MatrixRetargeter)
        backend.prepare(self.request)
        self.assertTrue(backend.prepared)
        self.assertFalse(cmds.keyframe("pelvis_JNT", query=True, keyframeCount=True))
        result = backend.bake()
        self.assertFalse(backend.prepared)
        self.report_motion(backend, result)
        points = sample_world_positions(["l_shoulder_JNT", "l_elbow_JNT", "l_wrist_JNT"], [1, 24])
        def angle(index):
            elbow = points["l_elbow_JNT"][index]
            a = [v - e for v, e in zip(points["l_shoulder_JNT"][index], elbow)]
            b = [v - e for v, e in zip(points["l_wrist_JNT"][index], elbow)]
            cosine = sum(x * y for x, y in zip(a, b)) / math.sqrt(
                sum(x * x for x in a) * sum(y * y for y in b))
            return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        self.assertGreater(abs(angle(1) - angle(0)), 10)
        self.assertEqual(source, self.source_curves())
        for joint in self.destination_joints():
            for attribute in ("rx", "ry", "rz"):
                self.assertEqual(cmds.keyframe(joint, attribute=attribute,
                                              query=True, keyframeCount=True), 48)

    def test_layer_preserves_existing_destination_animation(self):
        self.assert_preserved_layer(MatrixRetargeter)

    def test_no_root_motion_fractional_range_and_nondefault_units(self):
        cmds.currentUnit(linear="m")
        self.request.transfer_root_motion = False
        self.request.frame_range = (1.5, 4.0)
        self.request.sample_by = 0.5
        self.request.bake_to_layer = False
        before = sample_world_positions(["pelvis_JNT"], [1.5, 4])
        backend = self.backend(MatrixRetargeter)
        backend.prepare(self.request)
        backend.bake()
        after = sample_world_positions(["pelvis_JNT"], [1.5, 4])
        self.assertEqual(before, after)
        self.assertEqual(cmds.keyframe("l_wrist_JNT", attribute="rx", query=True,
                                       timeChange=True), [1.5, 2, 2.5, 3, 3.5, 4])
        self.assertFalse(cmds.keyframe("pelvis_JNT", attribute="ty", query=True, keyframeCount=True))

    def test_translation_with_scene_in_metres(self):
        cmds.currentUnit(linear="m")
        self.request.bake_to_layer = False
        backend = self.backend(MatrixRetargeter)
        backend.prepare(self.request)
        self.report_motion(backend, backend.bake())

    def test_single_undo(self):
        cmds.undoInfo(state=True, infinity=True)
        backend = self.backend(MatrixRetargeter)
        with undo_chunk("RigFlow: transfer (test)"):
            backend.prepare(self.request)
            result = backend.bake()
        cmds.undo()
        self.assertFalse(cmds.objExists(result.layer))
        self.assertFalse(cmds.keyframe("pelvis_JNT", query=True, keyframeCount=True))

    def test_rotate_order_and_angular_units(self):
        self.request.bake_to_layer = False
        backend = self.backend(MatrixRetargeter)
        backend.prepare(self.request)
        backend.bake()
        expected = sample_world_positions(self.destination_joints(), [1, 24, 48])
        for joint in self.destination_joints():
            cmds.cutKey(joint, attribute=["rx", "ry", "rz", "tx", "ty", "tz"], clear=True)
            cmds.setAttr(joint + ".rotate", 0, 0, 0)
            cmds.setAttr(joint + ".rotateOrder", 5)
        cmds.currentTime(1)
        cmds.setAttr("pelvis_JNT.translate", 0, 66, 0)
        cmds.currentUnit(angle="rad")
        backend.prepare(self.request)
        backend.bake()
        actual = sample_world_positions(self.destination_joints(), [1, 24, 48])
        for joint in expected:
            for p, q in zip(expected[joint], actual[joint]):
                for a, b in zip(p, q):
                    self.assertAlmostEqual(a, b, places=5)
        cmds.currentUnit(angle="deg")

    def test_scene_z_up_and_transformed_skeleton_parents(self):
        self.request.bake_to_layer = False
        cmds.upAxis(axis="z", rotateView=False)
        for root in (self.request.source_root, self.request.destination_root):
            group = cmds.group(empty=True)
            cmds.parent(root, group)
            cmds.setAttr(group + ".rotateX", 90)
        backend = self.backend(MatrixRetargeter)
        backend.prepare(self.request)
        result = backend.bake()
        points = sample_world_positions(["pelvis_JNT"], [1, 24])["pelvis_JNT"]
        self.assertAlmostEqual((points[1][2] - points[0][2]) / 44.974870, 0.66, places=5)
        self.assertLess(result.verification["max_bone_length_error"], 0.01)
