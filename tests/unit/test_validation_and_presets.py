import os
import shutil
import tempfile
import unittest

import fixtures
from rigflow.core.errors import MappingError
from rigflow.mapping.matcher import auto_map
from rigflow.mapping.model import JointMapping
from rigflow.mapping.presets import load_mapping, save_mapping
from rigflow.mapping.validation import validate_mapping
from rigflow.skeleton.model import JointInfo, Skeleton


class ValidationTest(unittest.TestCase):
    def test_clean_mapping_has_no_errors(self):
        source, destination = fixtures.mixamo(), fixtures.custom()
        mapping, _, _ = auto_map(source, destination)
        report = validate_mapping(mapping, source, destination)
        self.assertTrue(report.ok, [str(i) for i in report.errors])

    def test_finger_chains_do_not_trigger_hierarchy_warnings(self):
        source, destination = fixtures.mixamo(), fixtures.unreal()
        mapping, _, _ = auto_map(source, destination)
        report = validate_mapping(mapping, source, destination)
        hierarchy = [i for i in report.warnings if "not an expected parent" in i.message]
        self.assertEqual(hierarchy, [], [str(i) for i in hierarchy])

    def test_missing_required_role_is_error(self):
        spec = [e for e in fixtures.custom_spec() if e[0] != "r_wrist_JNT"]
        source, destination = fixtures.mixamo(), fixtures.build(spec, name="broken")
        mapping, _, _ = auto_map(source, destination)
        report = validate_mapping(mapping, source, destination)
        self.assertFalse(report.ok)
        self.assertTrue(any(i.role == "RightHand" for i in report.errors))

    def test_duplicate_destination_is_error(self):
        source, destination = fixtures.mixamo(), fixtures.custom()
        mapping, _, _ = auto_map(source, destination)
        mapping.set_manual("LeftFoot", "mixamorig:LeftFoot", "l_knee_JNT")  # already used by LeftLeg
        report = validate_mapping(mapping, source, destination)
        self.assertTrue(any("l_knee_JNT" in i.message for i in report.errors))

    def test_wrong_parent_is_warning(self):
        source, destination = fixtures.mixamo(), fixtures.custom()
        mapping, _, _ = auto_map(source, destination)
        mapping.set_manual("LeftHand", "mixamorig:LeftHand", "r_wrist_JNT")
        mapping.set_manual("RightHand", "mixamorig:RightHand", "l_wrist_JNT")
        report = validate_mapping(mapping, source, destination)
        self.assertTrue(report.ok)  # swapped hands are legal, just suspicious
        self.assertTrue(any(i.role == "LeftHand" and "not an expected parent" in i.message
                            for i in report.warnings))

    def test_unit_mismatch_is_warning(self):
        source = fixtures.mixamo()
        metres = Skeleton(
            [JointInfo(j.name, j.parent, tuple(c / 100.0 for c in j.world_position))
             for j in (source.joint(n) for n in source.joint_names)],
            name="metres",
        )
        mapping, _, _ = auto_map(source, metres)
        report = validate_mapping(mapping, source, metres)
        self.assertTrue(any("units" in i.message for i in report.warnings))

    def test_excluded_required_is_error(self):
        mapping, _, _ = auto_map(fixtures.mixamo(), fixtures.custom())
        mapping.set_excluded("Hips")
        report = validate_mapping(mapping)
        self.assertTrue(any(i.role == "Hips" for i in report.errors))

    def test_yellow_matches_are_warnings(self):
        mapping, _, _ = auto_map(fixtures.mixamo(), fixtures.nameless())
        report = validate_mapping(mapping)
        self.assertTrue(report.ok)
        self.assertTrue(report.warnings)


class PresetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rigflow_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_round_trip(self):
        mapping, _, _ = auto_map(fixtures.mixamo(), fixtures.custom())
        mapping.set_manual("LeftHand", "mixamorig:LeftHand", "l_wrist_JNT")
        mapping.set_excluded("Spine1")
        path = os.path.join(self.tmp, "nested", "mixamo_to_custom.rigflow.json")
        save_mapping(mapping, path)
        loaded = load_mapping(path)
        self.assertEqual(loaded.source_name, "mixamo")
        self.assertEqual(loaded.destination_name, "custom")
        self.assertEqual(loaded.manual["LeftHand"], ("mixamorig:LeftHand", "l_wrist_JNT"))
        self.assertTrue(loaded.matches["LeftHand"].manual)
        self.assertIn("Spine1", loaded.excluded)
        self.assertEqual(
            [m.role for m in loaded.sorted_matches()],
            [m.role for m in mapping.sorted_matches()],
        )
        self.assertEqual(loaded.complete_pairs(), mapping.complete_pairs())

    def test_invalid_files(self):
        with self.assertRaises(MappingError):
            load_mapping(os.path.join(self.tmp, "missing.json"))
        bad = os.path.join(self.tmp, "bad.json")
        with open(bad, "w") as handle:
            handle.write("{not json")
        with self.assertRaises(MappingError):
            load_mapping(bad)
        other = os.path.join(self.tmp, "other.json")
        with open(other, "w") as handle:
            handle.write('{"format": "something-else"}')
        with self.assertRaises(MappingError):
            load_mapping(other)

    def test_dict_round_trip_without_disk(self):
        mapping = JointMapping("a", "b")
        mapping.set_auto("Hips", "hips_a", "hips_b", 0.95)
        mapping.set_auto("Head", "head_a", None, 0.0)
        clone = JointMapping.from_dict(mapping.to_dict())
        self.assertEqual(clone.matches["Hips"].status, mapping.matches["Hips"].status)
        self.assertEqual(clone.matches["Head"].status.value, "red")


if __name__ == "__main__":
    unittest.main()
