"""Skeleton snapshots, rest restoration and real-scene mapping acceptance."""

from __future__ import annotations

import unittest

from maya import cmds

import scene_fixtures as sf
import fixtures
from rigflow.core.errors import SceneError
from rigflow.mapping import auto_map
from rigflow.mapping.model import MatchStatus
from rigflow.scene import read_skeleton, read_skeleton_rest
from rigflow.skeleton.roles import REQUIRED_ROLES


class SkeletonReaderTests(unittest.TestCase):
    def setUp(self):
        sf.new_scene()
        self.created = sf.build_skeleton(fixtures.mixamo_spec())
        self.root = self.created["mixamorig:Hips"]

    def test_positions_orientations_and_animation_flags(self):
        skeleton = read_skeleton(self.root)
        self.assertEqual(len(skeleton), 65)
        self.assertEqual(skeleton.roots, ["mixamorig:Hips"])
        self.assertEqual(skeleton.name, "mixamorig")
        for name, parent, position in fixtures.mixamo_spec():
            joint = skeleton.joint(name)
            self.assertEqual(joint.parent, parent or None)
            for actual, expected in zip(joint.world_position, position):
                self.assertAlmostEqual(actual, expected, delta=1e-4)
            matrix = cmds.xform(name, query=True, worldSpace=True, matrix=True)
            self.assertEqual(joint.world_orient, tuple(matrix[i] for i in (0, 1, 2, 4, 5, 6, 8, 9, 10)))
            self.assertFalse(joint.animated)
        sf.animate_jump(self.created, sf.mixamo_roles())
        animated = read_skeleton(self.root)
        self.assertTrue(all(animated.joint(n).animated for n in animated.joint_names))

    def test_rest_read_preserves_animated_scene(self):
        sf.animate_jump(self.created, sf.mixamo_roles())
        cmds.currentTime(24)
        before = cmds.xform(self.root, query=True, worldSpace=True, translation=True)
        keys = cmds.keyframe(query=True, keyframeCount=True)
        connections = cmds.listConnections(self.root, connections=True, plugs=True)
        selection = cmds.ls(selection=True, long=True)
        skeleton = read_skeleton_rest(self.root, stance_time=1)
        for actual, expected in zip(skeleton.joint(self.root).world_position, (0, 100, 0)):
            self.assertAlmostEqual(actual, expected, delta=1e-4)
        self.assertEqual(cmds.currentTime(query=True), 24)
        self.assertGreater(before[1], 100)
        self.assertEqual(cmds.xform(self.root, query=True, worldSpace=True, translation=True), before)
        self.assertEqual(cmds.keyframe(query=True, keyframeCount=True), keys)
        self.assertEqual(cmds.listConnections(self.root, connections=True, plugs=True), connections)
        self.assertEqual(cmds.ls(selection=True, long=True), selection)

    def test_required_roles_map_green(self):
        custom = sf.build_skeleton(fixtures.custom_spec())
        mapping, _, _ = auto_map(read_skeleton(self.root), read_skeleton(custom["root_JNT"]))
        for role in REQUIRED_ROLES:
            self.assertEqual(mapping.matches[role].status, MatchStatus.GREEN, role)
        self.assertEqual(mapping.matches["LeftArm"].destination, "l_shoulder_JNT")

    def test_invalid_root_and_nondefault_units(self):
        with self.assertRaises(SceneError):
            read_skeleton("missing")
        cmds.currentUnit(linear="m")
        cmds.upAxis(axis="z", rotateView=False)
        skeleton = read_skeleton(self.root, name="source")
        self.assertEqual((skeleton.name, skeleton.linear_unit, skeleton.up_axis), ("source", "m", "z"))
