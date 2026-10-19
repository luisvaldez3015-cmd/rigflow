"""Real Maya fit, skin binding, undo and animation-transfer pipeline coverage."""

from __future__ import annotations

import math
import unittest

from maya import cmds

import scene_fixtures as sf
from rigflow.core.errors import SceneError
from rigflow.mapping import auto_map
from rigflow.mapping.model import MatchStatus
from rigflow.retargeting import RetargetRequest, get_retargeter
from rigflow.rigging import bind_skeleton, fit_skeleton, remove_fit
from rigflow.scene import has_animation, read_skeleton_rest, rest_pose, undo_chunk
from rigflow.scene.demo import build_demo_scene
from rigflow.skeleton.roles import REQUIRED_ROLES


def joint_bounds(joints):
    points = [sf.world_position(j) for j in joints]
    return [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]


class RiggingTransferTests(unittest.TestCase):
    def setUp(self):
        sf.new_scene()
        self.demo = build_demo_scene()
        self.mesh = cmds.duplicate(self.demo.destination_mesh, name="static_body_GEO")[0]
        # Maya retains the skinned original's locked transform channels on duplication.
        cmds.setAttr(self.mesh + ".translateX", lock=False)
        cmds.move(200, 0, 0, self.mesh, relative=True, worldSpace=True)
        self.assertAlmostEqual(cmds.getAttr(self.mesh + ".translateX"), 200)
        self.backends = []

    def tearDown(self):
        for backend in self.backends:
            backend.cleanup()
        cmds.undoInfo(state=False)
        sf.new_scene()

    def test_fit_geometry_orientations_and_source_are_preserved(self):
        joints = list(self.demo.source_joints.values())
        cmds.currentTime(24)
        before = {j: sf.world_position(j) for j in joints}
        keys = {j: cmds.keyframe(j, query=True, keyframeCount=True) for j in joints}
        with undo_chunk("Read source stance for test"):
            with rest_pose(joints, stance_time=1):
                source_bounds = joint_bounds(joints)
                stance = {j: sf.world_position(j) for j in joints}
                orient = {j: (cmds.getAttr(j + ".jointOrient"), cmds.getAttr(j + ".rotate"),
                              cmds.getAttr(j + ".radius")) for j in joints}
        mesh_bounds = cmds.exactWorldBoundingBox(self.mesh)
        expected_scale = (mesh_bounds[4] - mesh_bounds[1]) / (source_bounds[4] - source_bounds[1])
        cmds.namespace(add="artist")
        cmds.namespace(setNamespace=":artist")
        fit = fit_skeleton(self.demo.source_root, [self.mesh], namespace="fitted", stance_time=1)
        self.assertEqual(cmds.namespaceInfo(currentNamespace=True, absoluteName=True), ":artist")
        cmds.namespace(setNamespace=":")
        self.assertEqual(cmds.currentTime(query=True), 24)
        self.assertEqual(len(fit.joints), len(joints))
        self.assertEqual(set(fit.source_joints), set(joints))
        self.assertFalse(cmds.listRelatives(fit.root, parent=True))
        self.assertTrue(all(j.startswith("fitted:") for j in fit.joints))
        self.assertTrue(cmds.namespace(exists="fitted"))
        self.assertFalse(any(has_animation(j) for j in fit.joints))
        self.assertFalse(any(cmds.listConnections(j, source=True, destination=False, type="animCurve")
                             for j in fit.joints))
        self.assertAlmostEqual(fit.scale, expected_scale, delta=1e-6)
        bounds = joint_bounds(fit.joints)
        self.assertAlmostEqual(bounds[1], mesh_bounds[1], delta=1e-4)
        for i in (0, 2):
            self.assertAlmostEqual((bounds[i] + bounds[i + 3]) / 2,
                                   (mesh_bounds[i] + mesh_bounds[i + 3]) / 2, delta=1e-4)
        paired = dict(zip(fit.source_joints, fit.joints))
        for source, fitted in paired.items():
            for attr, expected in (("jointOrient", orient[source][0]), ("rotate", orient[source][1])):
                for actual, value in zip(cmds.getAttr(fitted + "." + attr)[0], expected[0]):
                    self.assertAlmostEqual(actual, value, delta=1e-10)
            self.assertAlmostEqual(cmds.getAttr(fitted + ".radius"), orient[source][2] * fit.scale)
            parents = cmds.listRelatives(source, parent=True) or []
            if parents and parents[0] in paired:
                length = math.dist(stance[source], stance[parents[0]])
                fitted_length = math.dist(sf.world_position(fitted), sf.world_position(paired[parents[0]]))
                if length > 1e-10:
                    self.assertAlmostEqual(fitted_length / length, fit.scale, delta=1e-6)
            self.assertEqual(sf.world_position(source), before[source])
            self.assertEqual(cmds.keyframe(source, query=True, keyframeCount=True), keys[source])
        print("RIG_FIT_METRICS scale={:.12f} joints={} mesh_height={:.9f}".format(
            fit.scale, len(fit.joints), mesh_bounds[4] - mesh_bounds[1]))

    def test_fit_ignores_intermediate_shapes_of_a_duplicated_skinned_mesh(self):
        # Pose the skinned original, then duplicate it: the copy carries the
        # deformed shape plus an intermediate "Orig" shape at the rest position.
        cmds.setAttr(self.demo.destination_joints["pelvis_JNT"] + ".translateZ", 60)
        cmds.setAttr(self.demo.destination_joints["pelvis_JNT"] + ".translateY", 96)
        posed = cmds.duplicate(self.demo.destination_mesh, name="posed_body_GEO")[0]
        shapes = cmds.listRelatives(posed, shapes=True, fullPath=True)
        visible = [s for s in shapes if not cmds.getAttr(s + ".intermediateObject")]
        self.assertEqual(len(shapes), 2)
        self.assertEqual(len(visible), 1)
        visible_bounds = cmds.exactWorldBoundingBox(visible)
        union_bounds = cmds.exactWorldBoundingBox(posed)
        self.assertNotEqual([round(v, 3) for v in visible_bounds], [round(v, 3) for v in union_bounds])
        fit = fit_skeleton(self.demo.source_root, [posed], namespace="posed")
        bounds = joint_bounds(fit.joints)
        self.assertAlmostEqual(bounds[1], visible_bounds[1], delta=1e-4)
        self.assertAlmostEqual(bounds[4], visible_bounds[4], delta=1e-4)
        for i in (0, 2):
            self.assertAlmostEqual((bounds[i] + bounds[i + 3]) / 2,
                                   (visible_bounds[i] + visible_bounds[i + 3]) / 2, delta=1e-4)

    def test_fit_is_one_undo_step_without_outer_chunk(self):
        cmds.undoInfo(state=True, infinity=True)
        before = set(cmds.ls(long=True))
        fit = fit_skeleton(self.demo.source_root, [self.mesh], namespace="undo_fit")
        cmds.undo()
        self.assertFalse(any(cmds.objExists(j) for j in fit.joints))
        self.assertFalse(cmds.namespace(exists="undo_fit"))
        self.assertEqual(set(cmds.ls(long=True)), before)

    def test_root_namespace_name_clashes_and_non_joint_descendants(self):
        cmds.createNode("transform", name="Hips")
        control = cmds.circle(name="source_CTRL", constructionHistory=False)[0]
        cmds.parent(control, self.demo.source_root)
        cmds.namespace(add="artist")
        cmds.namespace(setNamespace=":artist")
        fit = fit_skeleton(self.demo.source_root, [self.mesh])
        self.assertEqual(cmds.namespaceInfo(currentNamespace=True, absoluteName=True), ":artist")
        cmds.namespace(setNamespace=":")
        self.assertNotEqual(fit.root, "Hips")
        self.assertTrue(all(":" not in j for j in fit.joints))
        descendants = cmds.listRelatives(fit.root, allDescendents=True, fullPath=True) or []
        self.assertTrue(all(cmds.nodeType(j) == "joint" for j in descendants))
        self.assertTrue(cmds.objExists(control))

    def test_bind_normalized_weights_deformation_and_repeated_removal(self):
        fit = fit_skeleton(self.demo.source_root, [self.mesh], namespace="bound")
        self.assertIs(bind_skeleton(fit, [self.mesh]), fit)
        self.assertEqual(len(fit.skin_clusters), 1)
        cluster = fit.skin_clusters[0]
        self.assertEqual(cmds.nodeType(cluster), "skinCluster")
        self.assertEqual(set(cmds.skinCluster(cluster, query=True, influence=True)), set(fit.joints))
        for vertex in (0, 10, cmds.polyEvaluate(self.mesh, vertex=True) - 1):
            weights = cmds.skinPercent(cluster, "{}.vtx[{}]".format(self.mesh, vertex), query=True, value=True)
            self.assertAlmostEqual(sum(weights), 1, delta=1e-4)
        before = cmds.exactWorldBoundingBox(self.mesh)
        vertex_before = cmds.pointPosition(self.mesh + ".vtx[0]", world=True)
        cmds.move(12, 0, 0, fit.root, relative=True, worldSpace=True)
        after = cmds.exactWorldBoundingBox(self.mesh)
        vertex_after = cmds.pointPosition(self.mesh + ".vtx[0]", world=True)
        # Transform bounds also include the undeformed intermediate shapes.
        self.assertNotEqual(after, before)
        self.assertAlmostEqual(vertex_after[0] - vertex_before[0], 12, delta=1e-4)
        source = {j: sf.world_position(j) for j in self.demo.source_joints.values()}
        remove_fit(fit)
        remove_fit(fit)
        self.assertFalse(cmds.objExists(cluster))
        self.assertFalse(any(cmds.objExists(j) for j in fit.joints))
        self.assertTrue(cmds.objExists(self.mesh))
        for joint, position in source.items():
            self.assertEqual(sf.world_position(joint), position)
        self.assertTrue(cmds.objExists("destination_body_skinCluster"))

    def test_parent_groups_are_removed_without_reorienting_joints(self):
        group = cmds.createNode("transform", name="sourceGroup")
        cmds.setAttr(group + ".rotate", 12, 30, 5)
        root = cmds.createNode("joint", name="groupedRoot", parent=group)
        cmds.setAttr(root + ".translate", 0, 10, 0)
        cmds.setAttr(root + ".jointOrient", 10, 20, 0)
        between = cmds.createNode("transform", name="between", parent=root)
        cmds.setAttr(between + ".translate", 3, 8, 0)
        cmds.setAttr(between + ".rotateZ", 30)
        child = cmds.createNode("joint", name="groupedChild", parent=between)
        cmds.setAttr(child + ".translate", 2, 10, 0)
        cmds.setAttr(child + ".jointOrient", 5, 0, 15)
        source = {j: sf.world_position(j) for j in (root, child)}
        fit = fit_skeleton(root, [self.mesh], namespace="grouped")
        self.assertEqual(len(fit.joints), 2)
        self.assertFalse(cmds.listRelatives(fit.root, parent=True))
        self.assertEqual(cmds.listRelatives(fit.joints[1], parent=True), [fit.root])
        for source_joint, fitted in zip(fit.source_joints, fit.joints):
            for actual, expected in zip(cmds.getAttr(fitted + ".jointOrient")[0],
                                        cmds.getAttr(source_joint + ".jointOrient")[0]):
                self.assertAlmostEqual(actual, expected, delta=1e-10)
            self.assertEqual(sf.world_position(source_joint), source[source_joint])
        self.assertAlmostEqual(math.dist(*(sf.world_position(j) for j in fit.joints))
                               / math.dist(source[root], source[child]), fit.scale, delta=1e-6)

    def test_fit_rejects_no_mesh_skinned_mesh_and_zero_heights(self):
        for meshes in ([], [self.demo.destination_mesh]):
            with self.assertRaises(SceneError) as error:
                fit_skeleton(self.demo.source_root, meshes)
            self.assertTrue(error.exception.hint)
        flat = cmds.polyPlane(axis=(0, 1, 0), constructionHistory=False)[0]
        with self.assertRaises(SceneError) as error:
            fit_skeleton(self.demo.source_root, [flat])
        self.assertIn("Mesh height", str(error.exception))
        cmds.select(clear=True)
        root = cmds.joint(name="pointJoint")
        before = set(cmds.ls(long=True))
        with self.assertRaises(SceneError) as error:
            fit_skeleton(root, [self.mesh], namespace="failed_fit")
        self.assertIn("Skeleton height", str(error.exception))
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertFalse(cmds.namespace(exists="failed_fit"))

    def test_z_up_fit_uses_scene_height_axis(self):
        cmds.upAxis(axis="z", rotateView=False)
        fit = fit_skeleton(self.demo.source_root, [self.mesh], namespace="zup")
        bounds = joint_bounds(fit.joints)
        mesh = cmds.exactWorldBoundingBox(self.mesh)
        self.assertAlmostEqual(bounds[2], mesh[2], delta=1e-4)
        self.assertAlmostEqual(bounds[5], mesh[5], delta=1e-4)
        for i in (0, 1):
            self.assertAlmostEqual((bounds[i] + bounds[i + 3]) / 2,
                                   (mesh[i] + mesh[i + 3]) / 2, delta=1e-4)

    def test_fitted_bound_skeleton_maps_and_bakes_with_default_backend(self):
        fit = fit_skeleton(self.demo.source_root, [self.mesh], namespace="transfer", stance_time=1)
        bind_skeleton(fit, [self.mesh])
        mapping, _, _ = auto_map(read_skeleton_rest(self.demo.source_root), read_skeleton_rest(fit.root))
        self.assertEqual(len(REQUIRED_ROLES), 15)
        for role in REQUIRED_ROLES:
            self.assertEqual(mapping.matches[role].status, MatchStatus.GREEN, role)
        backend = get_retargeter()
        self.backends.append(backend)
        backend.prepare(RetargetRequest(mapping, self.demo.source_root, fit.root, (1, 48),
                                         bake_to_layer=False, stance_time=1))
        self.assertTrue(backend.prepared)
        result = backend.bake()
        self.assertFalse(backend.prepared)
        self.assertIn(fit.root, result.baked_joints)
        self.assertTrue(has_animation(fit.root))
        self.assertEqual(cmds.keyframe(fit.root, attribute="translateY", query=True, keyframeCount=True), 48)
        self.assertNotEqual(sf.world_position(fit.root, 1), sf.world_position(fit.root, 24))
