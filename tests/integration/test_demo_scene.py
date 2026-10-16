import unittest

from maya import cmds

import scene_fixtures
from rigflow.mapping import auto_map, validate_mapping
from rigflow.mapping.model import MatchStatus
from rigflow.scene import find_meshes, find_skeleton_roots, inspect_scene, read_skeleton_rest
from rigflow.scene.demo import build_demo_scene
from rigflow.skeleton.roles import REQUIRED_ROLES


class DemoSceneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scene_fixtures.new_scene()
        cls.demo = build_demo_scene()

    def test_scene_content(self):
        self.assertEqual(find_skeleton_roots(), ["mixamorig:Hips", "root_JNT"])
        meshes = find_meshes()
        self.assertEqual(len(meshes), 1)
        self.assertTrue(meshes[0].skinned)
        self.assertGreater(meshes[0].vertex_count, 100)
        report = inspect_scene()
        self.assertEqual(report.frame_range, (1.0, 48.0))
        self.assertIn("jaw_CTRL", report.controls)

    def test_facial_setup_is_ignored_by_matching(self):
        source = read_skeleton_rest(self.demo.source_root)
        destination = read_skeleton_rest(self.demo.destination_root)
        mapping, _, labeling = auto_map(source, destination)
        ignored = labeling.ignored_joints()
        for joint in self.demo.facial_joints:
            self.assertIn(joint, ignored, joint)
        used = mapping.destination_joints_used()
        for joint in self.demo.facial_joints:
            self.assertNotIn(joint, used)

    def test_required_roles_green_and_valid(self):
        source = read_skeleton_rest(self.demo.source_root)
        destination = read_skeleton_rest(self.demo.destination_root)
        mapping, _, _ = auto_map(source, destination)
        for role in REQUIRED_ROLES:
            self.assertEqual(mapping.matches[role].status, MatchStatus.GREEN, role)
        report = validate_mapping(mapping, source, destination)
        self.assertTrue(report.ok, [str(i) for i in report.errors])
        self.assertEqual([i for i in report.warnings if "expected parent" in i.message], [])

    def test_proxy_mesh_blocks_are_rigid(self):
        """Each block follows one joint, so posing never stretches a polygon."""
        import math

        mesh = self.demo.destination_mesh

        def max_edge():
            best = 0.0
            for e in range(0, cmds.polyEvaluate(mesh, edge=True), 4):
                verts = cmds.ls(cmds.polyListComponentConversion(
                    "{}.e[{}]".format(mesh, e), toVertex=True), flatten=True)
                pts = [cmds.pointPosition(v, world=True) for v in verts]
                if len(pts) == 2:
                    best = max(best, math.dist(pts[0], pts[1]))
            return best

        before = max_edge()
        cmds.setAttr("l_knee_JNT.rotateX", 70)
        cmds.setAttr("pelvis_JNT.rotateY", 30)
        try:
            self.assertAlmostEqual(max_edge(), before, delta=0.05)
        finally:
            cmds.setAttr("l_knee_JNT.rotateX", 0)
            cmds.setAttr("pelvis_JNT.rotateY", 0)

    def test_source_is_animated_and_offset(self):
        cmds.currentTime(24)
        hips = cmds.xform(self.demo.source_root, q=True, worldSpace=True, translation=True)
        self.assertLess(hips[0], -100.0)  # moved aside so both characters are visible
        self.assertGreater(hips[1], 130.0)  # mid-jump
        cmds.currentTime(1)


if __name__ == "__main__":
    unittest.main()
