import unittest

from rigflow.skeleton.roles import (
    REQUIRED_ROLES,
    Side,
    display_name,
    is_valid_role,
    mirror_role,
    parse_role,
    role_name,
    sort_roles,
    template_ancestor_parts,
)
from rigflow.utils.strings import namespace_of, short_name, split_tokens


class SplitTokensTest(unittest.TestCase):
    def test_camel_case_and_digits(self):
        self.assertEqual(split_tokens("LeftHandIndex1"), ["left", "hand", "index", "1"])
        self.assertEqual(split_tokens("mixamorig:RightForeArm"), ["right", "fore", "arm"])

    def test_separators(self):
        self.assertEqual(split_tokens("upperarm_twist_01_l"), ["upperarm", "twist", "01", "l"])
        self.assertEqual(split_tokens("Bip01 L Thigh"), ["bip", "01", "l", "thigh"])
        self.assertEqual(split_tokens("|grp|char:l_wrist_JNT"), ["l", "wrist", "jnt"])

    def test_daz_glued_prefix(self):
        self.assertEqual(split_tokens("lShldrBend"), ["l", "shldr", "bend"])

    def test_short_name_and_namespace(self):
        self.assertEqual(short_name("|grp|mixamorig:LeftArm"), "LeftArm")
        self.assertEqual(namespace_of("rig:sub:LeftArm"), "rig:sub")
        self.assertEqual(namespace_of("LeftArm"), "")


class RolesTest(unittest.TestCase):
    def test_build_and_parse(self):
        self.assertEqual(role_name("Spine"), "Spine")
        self.assertEqual(role_name("Spine", index=2), "Spine2")
        self.assertEqual(role_name("Arm", Side.LEFT), "LeftArm")
        self.assertEqual(role_name("HandIndex", Side.RIGHT, 3), "RightHandIndex3")
        self.assertEqual(parse_role("RightHandIndex3"), (Side.RIGHT, "HandIndex", 3))
        self.assertEqual(parse_role("Spine"), (Side.CENTER, "Spine", 0))
        self.assertEqual(parse_role("Neck4"), (Side.CENTER, "Neck", 4))

    def test_invalid_roles(self):
        for bad in ("LeftSpine", "Arm", "LeftHandIndex0", "LeftHandIndex5", "Spine12", "LeftArm2", ""):
            self.assertFalse(is_valid_role(bad), bad)

    def test_mirror(self):
        self.assertEqual(mirror_role("LeftFoot"), "RightFoot")
        self.assertEqual(mirror_role("RightHandThumb2"), "LeftHandThumb2")
        self.assertEqual(mirror_role("Hips"), "Hips")

    def test_required_roles_are_valid(self):
        for role in REQUIRED_ROLES:
            self.assertTrue(is_valid_role(role), role)

    def test_sort_and_display(self):
        self.assertEqual(sort_roles(["LeftFoot", "Hips", "Head"]), ["Hips", "Head", "LeftFoot"])
        self.assertEqual(display_name("LeftForeArm"), "Left Fore Arm")
        self.assertEqual(display_name("Spine2"), "Spine 2")

    def test_template_ancestors(self):
        self.assertEqual(template_ancestor_parts("Hand"), ["ForeArm", "Arm", "Shoulder", "Spine", "Hips"])
        self.assertEqual(template_ancestor_parts("Hips"), [])


if __name__ == "__main__":
    unittest.main()
