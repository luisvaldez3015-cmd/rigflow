import unittest

import fixtures
from rigflow.skeleton.model import JointInfo, Skeleton
from rigflow.skeleton.naming import analyze_names
from rigflow.skeleton.topology import label_topology


def ignored_joints(skeleton):
    return {j for j, a in analyze_names(skeleton).items() if a.ignored}


class TopologyNamelessTest(unittest.TestCase):
    """The structural labeler must work with no usable names at all."""

    def setUp(self):
        self.skel = fixtures.nameless()
        self.result = label_topology(self.skel)

    def test_hips_and_chest(self):
        self.assertEqual(self.result.hips, "joint1")
        self.assertEqual(self.result.labels["joint1"], "Hips")
        self.assertEqual(self.result.chest, "joint4")  # Spine2 in the Mixamo layout

    def test_spine_neck_head(self):
        self.assertEqual(self.result.labels["joint2"], "Spine")
        self.assertEqual(self.result.labels["joint3"], "Spine1")
        self.assertEqual(self.result.labels["joint4"], "Spine2")
        self.assertEqual(self.result.labels["joint5"], "Neck")
        self.assertEqual(self.result.labels["joint6"], "Head")

    def test_arms_and_legs_with_sides(self):
        # Left side (positive X) joints come first in the nameless fixture.
        self.assertEqual(self.result.labels["joint7"], "LeftShoulder")
        self.assertEqual(self.result.labels["joint8"], "LeftArm")
        self.assertEqual(self.result.labels["joint9"], "LeftForeArm")
        self.assertEqual(self.result.labels["joint10"], "LeftHand")
        self.assertEqual(self.result.labels["joint11"], "LeftUpLeg")
        self.assertEqual(self.result.labels["joint12"], "LeftLeg")
        self.assertEqual(self.result.labels["joint13"], "LeftFoot")
        self.assertEqual(self.result.labels["joint14"], "LeftToeBase")
        self.assertEqual(self.result.joint_for("RightHand"), "joint18")
        self.assertEqual(self.result.joint_for("RightFoot"), "joint21")

    def test_all_required_roles_present(self):
        from rigflow.skeleton.roles import REQUIRED_ROLES

        for role in REQUIRED_ROLES:
            self.assertIsNotNone(self.result.joint_for(role), role)


class TopologyWithExclusionsTest(unittest.TestCase):
    def test_mixamo_with_ends_and_fingers_excluded(self):
        skel = fixtures.mixamo()
        result = label_topology(skel, exclude=ignored_joints(skel))
        self.assertEqual(result.joint_for("Hips"), "mixamorig:Hips")
        self.assertEqual(result.joint_for("Head"), "mixamorig:Head")
        self.assertEqual(result.joint_for("Neck"), "mixamorig:Neck")
        self.assertEqual(result.joint_for("LeftHand"), "mixamorig:LeftHand")
        self.assertEqual(result.joint_for("LeftShoulder"), "mixamorig:LeftShoulder")
        self.assertEqual(result.joint_for("RightToeBase"), "mixamorig:RightToeBase")
        self.assertNotIn("mixamorig:HeadTop_End", result.labels)

    def test_unreal_twists_and_ik_excluded(self):
        skel = fixtures.unreal()
        result = label_topology(skel, exclude=ignored_joints(skel))
        self.assertEqual(result.hips, "pelvis")
        self.assertEqual(result.chest, "spine_05")
        self.assertEqual(result.joint_for("Spine4"), "spine_05")
        self.assertEqual(result.joint_for("Neck1"), "neck_02")
        self.assertEqual(result.joint_for("Head"), "head")
        self.assertEqual(result.joint_for("LeftShoulder"), "clavicle_l")
        self.assertEqual(result.joint_for("LeftArm"), "upperarm_l")
        self.assertEqual(result.joint_for("LeftForeArm"), "lowerarm_l")
        self.assertEqual(result.joint_for("LeftHand"), "hand_l")
        self.assertEqual(result.joint_for("RightLeg"), "calf_r")
        self.assertEqual(result.joint_for("RightToeBase"), "ball_r")
        for twist in ("upperarm_twist_01_l", "calf_twist_02_r"):
            self.assertNotIn(twist, result.labels)

    def test_custom_arm_without_clavicle(self):
        skel = fixtures.custom()
        result = label_topology(skel, exclude=ignored_joints(skel))
        self.assertEqual(result.joint_for("LeftArm"), "l_shoulder_JNT")
        self.assertEqual(result.joint_for("LeftForeArm"), "l_elbow_JNT")
        self.assertEqual(result.joint_for("LeftHand"), "l_wrist_JNT")
        self.assertIsNone(result.joint_for("LeftShoulder"))
        self.assertEqual(result.joint_for("Spine2"), "chest_JNT")

    def test_mirrored_skeleton_flips_when_told(self):
        skel = fixtures.mixamo_mirrored()
        default = label_topology(skel, exclude=ignored_joints(skel))
        flipped = label_topology(skel, exclude=ignored_joints(skel), left_is_positive=False)
        self.assertEqual(default.joint_for("LeftArm"), "mixamorig:RightArm")
        self.assertEqual(flipped.joint_for("LeftArm"), "mixamorig:LeftArm")
        self.assertEqual(flipped.joint_for("RightFoot"), "mixamorig:RightFoot")


class TopologyRobustnessTest(unittest.TestCase):
    def test_empty_skeleton(self):
        result = label_topology(Skeleton([]))
        self.assertEqual(result.labels, {})
        self.assertTrue(result.notes)

    def test_single_chain_has_no_hips(self):
        skel = Skeleton([JointInfo("a", None, (0, 0, 0)), JointInfo("b", "a", (0, 10, 0)),
                         JointInfo("c", "b", (0, 20, 0))])
        result = label_topology(skel)
        self.assertIsNone(result.hips)
        self.assertTrue(any("hips" in n.lower() for n in result.notes))

    def test_prop_root_does_not_win(self):
        spec = fixtures.mixamo_spec(fingers=False, ends=False)
        spec.append(("sword", "", (30, 90, 10)))
        spec.append(("sword_tip", "sword", (30, 150, 10)))
        result = label_topology(fixtures.build(spec))
        self.assertEqual(result.hips, "mixamorig:Hips")


if __name__ == "__main__":
    unittest.main()
