"""Backend contract, validation, ownership and numeric helper integration tests."""

from __future__ import annotations

import unittest
from unittest import mock

from maya import cmds, mel

import scene_fixtures as scenes
from scene_fixtures import fixtures
from rigflow.core.errors import RetargetError, UnsupportedError
from rigflow.mapping.model import JointMapping
from rigflow.retargeting import (HumanIKRetargeter, MatrixRetargeter, RetargetRequest,
                                available_backends, get_retargeter)
from rigflow.retargeting.baker import create_override_layer
from rigflow.retargeting.verify import bone_length_error, sample_world_positions, travel


class RetargetFixture:
    """The same asymmetric skeleton pair for every backend test."""

    def setUp(self) -> None:
        scenes.new_scene()
        self.src = scenes.build_skeleton(fixtures.mixamo_spec(), orient="xyz")
        self.dst = scenes.build_skeleton(fixtures.custom_spec(), orient="yzx")
        scenes.animate_jump(self.src, scenes.mixamo_roles())
        self.mapping = JointMapping()
        for role in scenes.mixamo_roles().keys() & scenes.custom_roles().keys():
            self.mapping.set_auto(role, self.src[scenes.mixamo_roles()[role]],
                                  self.dst[scenes.custom_roles()[role]], 0.95)
        self.request = RetargetRequest(self.mapping, self.src["mixamorig:Hips"],
                                       self.dst["root_JNT"], (1, 48))
        self.backends = []

    def tearDown(self) -> None:
        for backend in self.backends:
            backend.cleanup()
        cmds.undoInfo(state=False)
        cmds.currentUnit(angle="deg")
        scenes.new_scene()

    def backend(self, cls):
        backend = cls()
        self.backends.append(backend)
        return backend

    def destination_joints(self):
        return [d for _, _, d in self.mapping.complete_pairs()]

    def source_curves(self):
        return {c: (cmds.keyframe(c, query=True, timeChange=True),
                    cmds.keyframe(c, query=True, valueChange=True))
                for c in (cmds.ls(type="animCurve") or [])
                if c.startswith("mixamorig:")}

    def existing_destination_keys(self):
        for frame, angle, x in ((1, 5.0, 3.0), (24, 12.0, 8.0), (48, -4.0, 2.0)):
            cmds.setKeyframe("l_shoulder_JNT", attribute="rotateZ", time=frame, value=angle)
            cmds.setKeyframe("pelvis_JNT", attribute="translateX", time=frame, value=x)
        cmds.currentTime(24)
        return (cmds.getAttr("l_shoulder_JNT.rotateZ"), cmds.getAttr("pelvis_JNT.translateX"))

    def assert_preserved_layer(self, cls):
        original = self.existing_destination_keys()
        curves = {c: (cmds.keyframe(c, query=True, timeChange=True),
                      cmds.keyframe(c, query=True, valueChange=True))
                  for c in cmds.ls(type="animCurve")}
        backend = self.backend(cls)
        backend.prepare(self.request)
        preview = (sample_world_positions(self.destination_joints(), [1, 24, 48])
                   if backend.name == "humanik" else None)
        result = backend.bake()
        if preview:
            baked = sample_world_positions(self.destination_joints(), [1, 24, 48])
            error = max(abs(a - b) for joint in preview
                        for p, q in zip(preview[joint], baked[joint]) for a, b in zip(p, q))
            self.assertLess(error, 1e-3)
        self.assertTrue(result.layer.startswith(self.request.layer_name))
        cmds.currentTime(24)
        retargeted = scenes.world_position("pelvis_JNT")
        self.assertGreater(retargeted[1], 80)
        cmds.setAttr(result.layer + ".mute", True)
        cmds.currentTime(1)
        cmds.currentTime(24)
        self.assertAlmostEqual(cmds.getAttr("l_shoulder_JNT.rotateZ"), original[0], delta=1e-3)
        self.assertAlmostEqual(cmds.getAttr("pelvis_JNT.translateX"), original[1], delta=1e-3)
        for curve, values in curves.items():
            self.assertEqual(cmds.keyframe(curve, query=True, timeChange=True), values[0])
            self.assertEqual(cmds.keyframe(curve, query=True, valueChange=True), values[1])
        cmds.setAttr(result.layer + ".mute", False)
        cmds.currentTime(1)
        cmds.currentTime(24)
        for actual, expected in zip(scenes.world_position("pelvis_JNT"), retargeted):
            self.assertAlmostEqual(actual, expected, delta=1e-3)

    def report_motion(self, backend, result):
        source = sample_world_positions(["mixamorig:Hips"], [1, 24])["mixamorig:Hips"]
        destination = sample_world_positions(["pelvis_JNT"], [1, 24])["pelvis_JNT"]
        rise = (destination[1][1] - destination[0][1]) / (source[1][1] - source[0][1])
        self.assertGreater(rise, 0.4)
        self.assertLess(rise, 1.0)
        self.assertLess(result.verification["max_bone_length_error"], 0.01)
        print("RETARGET_METRICS {} rise_ratio={:.9f} bone_error_cm={:.9g} elapsed_s={:.4f}".format(
            backend.name, rise, result.verification["max_bone_length_error"],
            result.verification["elapsed_s"]))


class TestRetargetCommon(RetargetFixture, unittest.TestCase):
    def test_backend_selection(self):
        available = {name: ok for name, ok, _ in available_backends()}
        self.assertEqual(available, {"humanik": True, "matrix": True})
        self.assertIsInstance(get_retargeter(), HumanIKRetargeter)
        self.assertIsInstance(get_retargeter("matrix"), MatrixRetargeter)
        with mock.patch.object(HumanIKRetargeter, "availability", return_value=(False, "missing")):
            self.assertIsInstance(get_retargeter(), MatrixRetargeter)
            with self.assertRaises(UnsupportedError):
                get_retargeter("humanik")
        with self.assertRaises(UnsupportedError):
            get_retargeter("invalid")

    def test_invalid_required_roles_leave_no_nodes(self):
        self.mapping.matches.pop("RightHand")
        before = set(cmds.ls())
        for cls in (HumanIKRetargeter, MatrixRetargeter):
            backend = self.backend(cls)
            with self.assertRaises(RetargetError) as error:
                backend.prepare(self.request)
            self.assertIn("RightHand", str(error.exception))
            self.assertEqual(error.exception.hint, "complete the mapping")
            self.assertEqual(set(cmds.ls()), before)
            self.assertFalse(backend.prepared)

    def test_excluded_required_role_is_not_transferable(self):
        self.mapping.set_excluded("RightHand")
        with self.assertRaises(RetargetError):
            self.backend(HumanIKRetargeter).prepare(self.request)

    def test_invalid_range_and_missing_joint(self):
        for frame_range, interval in (((48, 1), 1), ((1, 48), 0), ((1, float("nan")), 1)):
            self.request.frame_range, self.request.sample_by = frame_range, interval
            with self.assertRaises(RetargetError):
                self.backend(MatrixRetargeter).prepare(self.request)
        self.request.frame_range, self.request.sample_by = (1, 48), 1
        cmds.delete("r_wrist_JNT")
        with self.assertRaises(RetargetError):
            self.backend(HumanIKRetargeter).prepare(self.request)

    def test_failed_hik_prepare_cleans_only_own_nodes(self):
        # First run loads the MEL procedures, then retain an unrelated character.
        backend = self.backend(HumanIKRetargeter)
        backend.prepare(self.request)
        backend.cleanup()
        unrelated = mel.eval('hikCreateCharacter("unrelated_character")')
        before = set(cmds.ls())
        original = backend._characterize
        def fail_after_creation(name, slots):
            original(name, slots)
            raise RuntimeError("injected failure after character creation")
        with mock.patch.object(backend, "_characterize", side_effect=fail_after_creation):
            with self.assertRaises(RetargetError):
                backend.prepare(self.request)
        self.assertTrue(cmds.objExists(unrelated))
        self.assertEqual(set(cmds.ls()), before)

    def test_verification_converts_scene_units_and_restores_time(self):
        cmds.currentUnit(linear="m")
        cmds.currentTime(12)
        values = sample_world_positions(["mixamorig:Hips"], [1, 24])
        self.assertAlmostEqual(values["mixamorig:Hips"][0][1], 100, places=5)
        self.assertGreater(travel("mixamorig:Hips", [1, 24, 48]), 70)
        self.assertLess(bone_length_error(list(self.src.values()), [1, 24, 48]), 1e-6)
        self.assertEqual(cmds.currentTime(query=True), 12)

    def test_layer_names_do_not_replace_existing_layer(self):
        first = create_override_layer(self.request.layer_name)
        second = create_override_layer(self.request.layer_name)
        self.assertNotEqual(first, second)
        self.assertTrue(cmds.objExists(first))
