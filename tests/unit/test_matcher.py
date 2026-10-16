import unittest

import fixtures
from rigflow.mapping.matcher import auto_map, build_mapping, label_skeleton
from rigflow.mapping.model import MatchStatus
from rigflow.skeleton.roles import REQUIRED_ROLES


class LabelSkeletonTest(unittest.TestCase):
    def test_mixamo_all_agree(self):
        labeling = label_skeleton(fixtures.mixamo())
        self.assertEqual(labeling.convention, "Mixamo")
        for role in REQUIRED_ROLES:
            joint = labeling.joint_for(role)
            self.assertIsNotNone(joint, role)
            label = labeling.labels[joint]
            self.assertEqual(label.evidence, ("name", "topology"), role)
            self.assertGreaterEqual(label.confidence, 0.9, role)
        self.assertEqual(labeling.joint_for("LeftHandIndex3"), "mixamorig:LeftHandIndex3")
        self.assertEqual(labeling.ignored_joints()["mixamorig:HeadTop_End"], "end")

    def test_unreal_labels(self):
        labeling = label_skeleton(fixtures.unreal())
        roles = labeling.roles()
        self.assertEqual(roles["Hips"], "pelvis")
        self.assertEqual(roles["Spine4"], "spine_05")
        self.assertEqual(roles["LeftShoulder"], "clavicle_l")
        self.assertEqual(roles["LeftArm"], "upperarm_l")
        self.assertEqual(roles["RightHand"], "hand_r")
        self.assertEqual(roles["LeftToeBase"], "ball_l")
        self.assertEqual(roles["LeftHandIndex1"], "index_01_l")
        ignored = labeling.ignored_joints()
        self.assertEqual(ignored["ik_foot_l"], "control")
        self.assertEqual(ignored["upperarm_twist_01_l"], "twist")
        self.assertEqual(ignored["index_metacarpal_l"], "metacarpal")
        # "root" lost the Hips role to "pelvis" and is simply unassigned.
        self.assertIsNone(labeling.role_of("root"))

    def test_advanced_skeleton_ambiguity_resolved_by_topology(self):
        labeling = label_skeleton(fixtures.advanced_skeleton())
        roles = labeling.roles()
        self.assertEqual(roles["Hips"], "Root_M")
        self.assertEqual(roles["Spine2"], "Chest_M")
        self.assertEqual(roles["LeftShoulder"], "Scapula_L")
        self.assertEqual(roles["LeftArm"], "Shoulder_L")
        self.assertEqual(roles["LeftForeArm"], "Elbow_L")
        self.assertEqual(roles["LeftHand"], "Wrist_L")
        self.assertEqual(roles["RightUpLeg"], "Hip_R")
        self.assertEqual(roles["LeftHandThumb2"], "ThumbFinger2_L")
        self.assertEqual(labeling.ignored_joints()["Jaw_M"], "facial")
        self.assertGreaterEqual(labeling.confidence_of("Shoulder_L"), 0.8)

    def test_custom_destination(self):
        labeling = label_skeleton(fixtures.custom())
        roles = labeling.roles()
        self.assertEqual(roles["Hips"], "pelvis_JNT")
        self.assertEqual(roles["LeftArm"], "l_shoulder_JNT")
        self.assertEqual(roles["LeftForeArm"], "l_elbow_JNT")
        self.assertEqual(roles["LeftHand"], "l_wrist_JNT")
        self.assertEqual(roles["LeftUpLeg"], "l_hip_JNT")
        self.assertEqual(roles["RightToeBase"], "r_ball_JNT")
        self.assertEqual(roles["Spine2"], "chest_JNT")
        self.assertNotIn("LeftShoulder", roles)

    def test_nameless_is_yellow_but_complete(self):
        labeling = label_skeleton(fixtures.nameless())
        for role in REQUIRED_ROLES:
            joint = labeling.joint_for(role)
            self.assertIsNotNone(joint, role)
            self.assertEqual(labeling.labels[joint].evidence, ("topology",))
            self.assertLess(labeling.confidence_of(joint), 0.8)
            self.assertGreaterEqual(labeling.confidence_of(joint), 0.5)

    def test_mirrored_skeleton_sides_follow_names(self):
        labeling = label_skeleton(fixtures.mixamo_mirrored())
        self.assertEqual(labeling.joint_for("LeftArm"), "mixamorig:LeftArm")
        self.assertEqual(labeling.joint_for("RightFoot"), "mixamorig:RightFoot")
        self.assertTrue(any("flipped" in note.lower() for note in labeling.notes))
        self.assertGreaterEqual(labeling.confidence_of("mixamorig:LeftArm"), 0.9)


class BuildMappingTest(unittest.TestCase):
    def test_mixamo_to_custom(self):
        mapping, source, destination = auto_map(fixtures.mixamo(), fixtures.custom())
        for role in REQUIRED_ROLES:
            match = mapping.matches[role]
            self.assertTrue(match.complete, role)
            self.assertEqual(match.status, MatchStatus.GREEN, role)
        self.assertEqual(mapping.matches["LeftArm"].destination, "l_shoulder_JNT")
        self.assertEqual(mapping.matches["LeftShoulder"].status, MatchStatus.UNAVAILABLE)
        self.assertEqual(mapping.matches["LeftHandIndex1"].status, MatchStatus.UNAVAILABLE)
        self.assertFalse(mapping.has_blocking_issues)
        pairs = dict((r, (s, d)) for r, s, d in mapping.complete_pairs())
        self.assertEqual(pairs["Hips"], ("mixamorig:Hips", "pelvis_JNT"))
        self.assertEqual(pairs["RightFoot"], ("mixamorig:RightFoot", "r_ankle_JNT"))
        # Both skeletons have three spine joints, so the whole chain is mapped.
        self.assertTrue(mapping.matches["Spine2"].complete)
        self.assertNotIn("Spine3", mapping.matches)

    def test_unreal_to_mixamo_spine_lengths(self):
        mapping, _, _ = auto_map(fixtures.unreal(), fixtures.mixamo())
        self.assertTrue(mapping.matches["Spine"].complete)
        self.assertTrue(mapping.matches["Spine2"].complete)
        self.assertEqual(mapping.matches["Spine4"].status, MatchStatus.UNAVAILABLE)
        self.assertEqual(mapping.matches["Neck1"].status, MatchStatus.UNAVAILABLE)
        self.assertEqual(mapping.matches["Head"].status, MatchStatus.GREEN)

    def test_nameless_destination_is_yellow(self):
        mapping, _, _ = auto_map(fixtures.mixamo(), fixtures.nameless())
        for role in REQUIRED_ROLES:
            self.assertEqual(mapping.matches[role].status, MatchStatus.YELLOW, role)

    def test_missing_required_is_red(self):
        spec = [entry for entry in fixtures.custom_spec() if entry[0] != "r_wrist_JNT"]
        destination = fixtures.build(spec, name="no_right_hand")
        mapping, _, _ = auto_map(fixtures.mixamo(), destination)
        self.assertEqual(mapping.matches["RightHand"].status, MatchStatus.RED)
        self.assertTrue(mapping.has_blocking_issues)

    def test_manual_override_survives_recompute(self):
        source, destination = fixtures.mixamo(), fixtures.custom()
        mapping, src_lab, dst_lab = auto_map(source, destination)
        mapping.set_manual("LeftToeBase", "mixamorig:LeftToeBase", "l_ball_JNT")
        mapping.set_manual("LeftHand", "mixamorig:LeftHand", "l_elbow_JNT")
        mapping.set_excluded("Spine2")

        recomputed = build_mapping(src_lab, dst_lab, previous=mapping)
        hand = recomputed.matches["LeftHand"]
        self.assertTrue(hand.manual)
        self.assertEqual(hand.destination, "l_elbow_JNT")
        self.assertEqual(hand.status, MatchStatus.GREEN)
        self.assertEqual(hand.confidence, 1.0)
        self.assertEqual(recomputed.matches["Spine2"].status, MatchStatus.EXCLUDED)
        self.assertNotIn("Spine2", [r for r, _, _ in recomputed.complete_pairs()])

        recomputed.clear_manual("LeftHand")
        self.assertFalse(recomputed.matches["LeftHand"].manual)
        recomputed.set_excluded("Spine2", False)
        self.assertEqual(recomputed.matches["Spine2"].status, MatchStatus.GREEN)

    def test_summary_counts(self):
        mapping, _, _ = auto_map(fixtures.mixamo(), fixtures.custom())
        summary = mapping.summary()
        self.assertEqual(summary["red"], 0)
        self.assertGreaterEqual(summary["green"], len(REQUIRED_ROLES))
        self.assertGreater(summary["unavailable"], 0)


if __name__ == "__main__":
    unittest.main()
