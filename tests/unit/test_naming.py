import unittest

import fixtures
from rigflow.skeleton.naming import analyze_name, analyze_names, detect_convention
from rigflow.skeleton.roles import Side


class AnalyzeNameTest(unittest.TestCase):
    def role(self, name):
        return analyze_name(name).role

    def test_mixamo_names(self):
        self.assertEqual(self.role("mixamorig:Hips"), "Hips")
        self.assertEqual(self.role("mixamorig:LeftUpLeg"), "LeftUpLeg")
        self.assertEqual(self.role("mixamorig:LeftLeg"), "LeftLeg")
        self.assertEqual(self.role("mixamorig:RightForeArm"), "RightForeArm")
        self.assertEqual(self.role("mixamorig:LeftShoulder"), "LeftShoulder")
        self.assertEqual(self.role("mixamorig:LeftHandIndex1"), "LeftHandIndex1")
        self.assertEqual(self.role("mixamorig:RightHandThumb4"), "RightHandThumb4")
        self.assertEqual(self.role("mixamorig:LeftToeBase"), "LeftToeBase")

    def test_unreal_names(self):
        self.assertEqual(self.role("pelvis"), "Hips")
        self.assertEqual(self.role("clavicle_l"), "LeftShoulder")
        self.assertEqual(self.role("upperarm_l"), "LeftArm")
        self.assertEqual(self.role("lowerarm_r"), "RightForeArm")
        self.assertEqual(self.role("hand_l"), "LeftHand")
        self.assertEqual(self.role("thigh_r"), "RightUpLeg")
        self.assertEqual(self.role("calf_l"), "LeftLeg")
        self.assertEqual(self.role("foot_l"), "LeftFoot")
        self.assertEqual(self.role("ball_l"), "LeftToeBase")
        self.assertEqual(self.role("index_02_l"), "LeftHandIndex2")
        self.assertEqual(self.role("pinky_01_r"), "RightHandPinky1")

    def test_custom_and_other_conventions(self):
        self.assertEqual(self.role("l_wrist_JNT"), "LeftHand")
        self.assertEqual(self.role("l_elbow_JNT"), "LeftForeArm")
        self.assertEqual(self.role("r_knee_JNT"), "RightLeg")
        self.assertEqual(self.role("l_ankle_JNT"), "LeftFoot")
        self.assertEqual(self.role("l_hip_JNT"), "LeftUpLeg")  # sided hip = thigh
        self.assertEqual(self.role("Hip_L"), "LeftUpLeg")
        self.assertEqual(self.role("Wrist_R"), "RightHand")
        self.assertEqual(self.role("Scapula_L"), "LeftShoulder")
        self.assertEqual(self.role("Bip01 L Thigh"), "LeftUpLeg")
        self.assertEqual(self.role("Bip01 R Calf"), "RightLeg")
        self.assertEqual(self.role("Bip01 L Clavicle"), "LeftShoulder")
        self.assertEqual(self.role("Bip01 L UpperArm"), "LeftArm")
        self.assertEqual(self.role("LeftUpperArm"), "LeftArm")
        self.assertEqual(self.role("LeftLowerLeg"), "LeftLeg")
        self.assertEqual(self.role("lShldrBend"), "LeftArm")
        self.assertEqual(self.role("rForearmBend"), "RightForeArm")
        self.assertEqual(self.role("ThumbFinger2_L"), "LeftHandThumb2")

    def test_ambiguous_names(self):
        shoulder = analyze_name("l_shoulder_JNT")
        self.assertEqual(shoulder.role, "LeftShoulder")
        self.assertTrue(shoulder.ambiguous)
        self.assertIn("LeftArm", shoulder.candidate_roles())
        leg = analyze_name("leg_L")
        self.assertIn("LeftUpLeg", leg.candidate_roles())
        self.assertLess(leg.confidence, 0.9)

    def test_root_is_weak_hips_candidate(self):
        root = analyze_name("root")
        self.assertEqual(root.role, "Hips")
        self.assertLess(root.confidence, 0.5)

    def test_ignored_joints(self):
        self.assertEqual(analyze_name("mixamorig:HeadTop_End").ignored, "end")
        self.assertEqual(analyze_name("LeftToe_End").ignored, "end")
        self.assertEqual(analyze_name("upperarm_twist_01_l").ignored, "twist")
        self.assertEqual(analyze_name("Jaw_M").ignored, "facial")
        self.assertEqual(analyze_name("Eye_L").ignored, "facial")
        self.assertEqual(analyze_name("FACIAL_C_Jaw").ignored, "facial")
        self.assertEqual(analyze_name("ik_foot_l").ignored, "control")
        self.assertEqual(analyze_name("l_arm_CTRL").ignored, "control")
        self.assertEqual(analyze_name("index_metacarpal_l").ignored, "metacarpal")
        self.assertEqual(analyze_name("spine_04_latissimus_l").ignored, "helper")
        self.assertEqual(analyze_name("sword_JNT").ignored, "accessory")
        self.assertEqual(analyze_name("lBigToe").ignored, "toe_digit")
        self.assertIsNone(analyze_name("mixamorig:HeadTop_End").role)

    def test_side_detection(self):
        self.assertEqual(analyze_name("LeftArm").side, Side.LEFT)
        self.assertEqual(analyze_name("arm_R").side, Side.RIGHT)
        self.assertEqual(analyze_name("Spine1_M").side, Side.CENTER)
        self.assertTrue(analyze_name("Spine1_M").side_explicit)
        self.assertFalse(analyze_name("spine_01").side_explicit)

    def test_sided_part_without_side_has_no_role(self):
        analysis = analyze_name("wrist_JNT")
        self.assertEqual(analysis.part, "Hand")
        self.assertIsNone(analysis.role)


class ChainRenumberingTest(unittest.TestCase):
    def test_unreal_spine_renumbered_by_depth(self):
        analyses = analyze_names(fixtures.unreal())
        self.assertEqual(analyses["spine_01"].role, "Spine")
        self.assertEqual(analyses["spine_03"].role, "Spine2")
        self.assertEqual(analyses["spine_05"].role, "Spine4")
        self.assertEqual(analyses["neck_01"].role, "Neck")
        self.assertEqual(analyses["neck_02"].role, "Neck1")

    def test_advanced_skeleton_chest_is_last_spine(self):
        analyses = analyze_names(fixtures.advanced_skeleton())
        self.assertEqual(analyses["Spine1_M"].role, "Spine")
        self.assertEqual(analyses["Spine2_M"].role, "Spine1")
        self.assertEqual(analyses["Chest_M"].role, "Spine2")

    def test_mixamo_keeps_indices(self):
        analyses = analyze_names(fixtures.mixamo())
        self.assertEqual(analyses["mixamorig:Spine"].role, "Spine")
        self.assertEqual(analyses["mixamorig:Spine2"].role, "Spine2")


class ConventionTest(unittest.TestCase):
    def test_detection(self):
        self.assertEqual(detect_convention(fixtures.mixamo().joint_names), "Mixamo")
        self.assertEqual(detect_convention(fixtures.unreal().joint_names), "Unreal Engine / MetaHuman")
        self.assertEqual(detect_convention(fixtures.advanced_skeleton().joint_names), "AdvancedSkeleton")
        self.assertEqual(detect_convention(["Bip01 Pelvis", "Bip01 L Thigh"]), "3ds Max Biped")
        self.assertEqual(detect_convention(["Hips", "Spine", "LeftUpLeg", "LeftArm", "LeftForeArm"]), "HumanIK")
        self.assertEqual(detect_convention(fixtures.nameless().joint_names), "Unknown")


if __name__ == "__main__":
    unittest.main()
