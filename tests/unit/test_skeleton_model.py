import unittest

import fixtures
from rigflow.skeleton.model import JointInfo, Skeleton


class SkeletonModelTest(unittest.TestCase):
    def setUp(self):
        self.skel = fixtures.mixamo()

    def test_children_rebuilt_from_parents(self):
        kids = set(self.skel.children("mixamorig:Hips"))
        self.assertEqual(kids, {"mixamorig:Spine", "mixamorig:LeftUpLeg", "mixamorig:RightUpLeg"})
        self.assertEqual(self.skel.roots, ["mixamorig:Hips"])

    def test_queries(self):
        self.assertEqual(self.skel.depth("mixamorig:LeftHand"), 7)
        self.assertEqual(
            self.skel.ancestors("mixamorig:LeftForeArm")[:2],
            ["mixamorig:LeftArm", "mixamorig:LeftShoulder"],
        )
        self.assertTrue(self.skel.is_ancestor("mixamorig:Spine2", "mixamorig:LeftHandIndex4"))
        self.assertTrue(self.skel.is_leaf("mixamorig:HeadTop_End"))
        self.assertEqual(self.skel.subtree_size("mixamorig:LeftHand"), 21)

    def test_geometry(self):
        self.assertAlmostEqual(self.skel.height(), 180.0 - 1.0)
        self.assertAlmostEqual(self.skel.bone_length("mixamorig:LeftForeArm"), 27.0)
        self.assertEqual(self.skel.bone_length("mixamorig:Hips"), 0.0)

    def test_main_chain(self):
        chain = self.skel.main_chain("mixamorig:LeftUpLeg")
        self.assertEqual(
            chain,
            ["mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:LeftFoot",
             "mixamorig:LeftToeBase", "mixamorig:LeftToe_End"],
        )

    def test_orphan_parent_becomes_root(self):
        skel = Skeleton([JointInfo("a", parent="missing_group"), JointInfo("b", parent="a")])
        self.assertEqual(skel.roots, ["a"])
        self.assertEqual(skel.main_root(), "a")

    def test_duplicate_names_rejected(self):
        with self.assertRaises(ValueError):
            Skeleton([JointInfo("a"), JointInfo("a")])

    def test_round_trip(self):
        data = self.skel.to_dict()
        clone = Skeleton.from_dict(data)
        self.assertEqual(len(clone), len(self.skel))
        self.assertEqual(clone.children("mixamorig:Hips"), self.skel.children("mixamorig:Hips"))
        self.assertEqual(clone.position("mixamorig:LeftHand"), (72.0, 148.0, 0.0))


if __name__ == "__main__":
    unittest.main()
