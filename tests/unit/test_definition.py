"""Independent definitions preserve the automatic opposite side and preset compatibility."""
import unittest
from rigflow.mapping.model import JointMapping
from rigflow.mapping.matcher import build_mapping
from rigflow.mapping.definition import progress, slot_state
from rigflow.mapping.model import SkeletonLabeling, JointLabel


class DefinitionTests(unittest.TestCase):
    def test_edit_and_move_only_one_side(self):
        mapping = JointMapping()
        mapping.set_auto("Hips", "a", "b", .9)
        mapping.set_auto("Spine", "c", "d", .9)
        self.assertEqual(mapping.set_definition("Spine", "source", "a"), ["Hips"])
        self.assertIsNone(mapping.matches["Hips"].source)
        self.assertEqual(mapping.matches["Hips"].destination, "b")
        self.assertEqual(mapping.matches["Spine"].destination, "d")
        self.assertEqual(mapping.manual_sides["Spine"], {"source"})
        with self.assertRaises(ValueError):
            mapping.set_definition("Hips", "unknown", "a")

    def test_autodetect_keeps_manual_side_and_updates_other(self):
        src = SkeletonLabeling(labels={"a": JointLabel("a", "Hips", .95)})
        dst = SkeletonLabeling(labels={"b": JointLabel("b", "Hips", .95)})
        mapping = build_mapping(src, dst)
        mapping.set_definition("Hips", "source", "manual")
        dst.labels = {"new": JointLabel("new", "Hips", .95)}
        refreshed = build_mapping(src, dst, mapping)
        self.assertEqual(refreshed.matches["Hips"].source, "manual")
        self.assertEqual(refreshed.matches["Hips"].destination, "new")
        refreshed.set_definition("Hips", "source", None)
        self.assertIsNone(build_mapping(src, dst, refreshed).matches["Hips"].source)

    def test_presets_roundtrip_old_and_new_overrides(self):
        mapping = JointMapping()
        mapping.set_auto("Hips", "a", "b", .95)
        mapping.set_definition("Hips", "destination", "manual")
        clone = JointMapping.from_dict(mapping.to_dict())
        self.assertEqual(clone.manual_sides, {"Hips": {"destination"}})
        clone.set_auto("Hips", "new", "newB", .95)
        self.assertEqual((clone.matches["Hips"].source, clone.matches["Hips"].destination), ("new", "manual"))
        # The unlocked side may have changed since the manual tuple was recorded.
        second_clone = JointMapping.from_dict(clone.to_dict())
        self.assertEqual(second_clone.matches["Hips"].source, "new")
        legacy = mapping.to_dict()
        legacy.pop("manual_sides")
        clone = JointMapping.from_dict(legacy)
        clone.set_auto("Hips", "new", "newB", .95)
        self.assertEqual((clone.matches["Hips"].source, clone.matches["Hips"].destination), ("a", "manual"))

    def test_progress_and_states_belong_to_each_model(self):
        mapping = JointMapping()
        mapping.set_auto("Hips", "a", None, 0)
        labels = SkeletonLabeling(labels={"a": JointLabel("a", "Hips", .95)})
        self.assertEqual(progress(mapping, "source", {"a"}), 1)
        self.assertEqual(progress(mapping, "destination", {"b"}), 0)
        self.assertEqual(slot_state(mapping, "Hips", "source", {"a"}, labels), "assigned")
        self.assertEqual(slot_state(mapping, "Hips", "destination", {"b"}), "required")
        self.assertEqual(slot_state(mapping, "Spine3", "source", {"a"}), "empty")
        labels.labels["a"].confidence = .3
        self.assertEqual(slot_state(mapping, "Hips", "source", {"a"}, labels), "review")
        self.assertEqual(slot_state(mapping, "Hips", "source", {"other"}), "invalid")
        mapping.set_definition("Hips", "source", "a")
        self.assertEqual(slot_state(mapping, "Hips", "source", {"a"}, labels), "assigned")
