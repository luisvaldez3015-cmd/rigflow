"""Rest-pose similarity, region feedback and source weight copy in real Maya."""
import unittest

from maya import cmds

import scene_fixtures as sf
from rigflow.core.errors import SceneError
from rigflow.scene.demo import build_demo_scene
from rigflow.scene.similarity import (compare_meshes, dag_path, skin_function,
                                      vertex_component, surfaces)
from rigflow.rigging.transfer import fit_skeleton, bind_skeleton


class SimilarityTests(unittest.TestCase):
    def setUp(self):
        sf.new_scene()
        self.demo = build_demo_scene(with_face=False)
        self.source = self.demo.destination_mesh
        self.copy = cmds.duplicate(self.source, name="same_body")[0]
        for attr in ("translate", "scale"):
            for axis in "XYZ":
                cmds.setAttr(self.copy + "." + attr + axis, lock=False)

    def tearDown(self):
        cmds.undoInfo(state=False)
        sf.new_scene()

    def compare(self, mesh=None):
        return compare_meshes([self.source], [mesh or self.copy], self.demo.destination_root)

    def test_duplicate_shifted_scaled_and_intermediates(self):
        self.assertEqual(len(cmds.listRelatives(self.copy, shapes=True)), 2)
        cmds.setAttr(self.copy + ".scale", 1.7, 1.7, 1.7)
        cmds.setAttr(self.copy + ".translate", 230, 17, -50)
        result = self.compare()
        self.assertAlmostEqual(result.score, 100, delta=0.01)
        self.assertTrue(result.matches)
        self.assertEqual(result.differing, [])

    def test_z_up_normalization_uses_scene_preferences(self):
        cmds.upAxis(axis="z", rotateView=False)
        cmds.setAttr(self.copy + ".scale", 1.3, 1.3, 1.3)
        cmds.setAttr(self.copy + ".translate", 60, 15, 28)
        self.assertAlmostEqual(self.compare().score, 100, delta=0.01)

    def test_different_head_is_named_but_body_still_matches(self):
        surface = surfaces([self.copy])[0][0]
        # Only widen the head, keeping height and model centre unchanged.
        for i, point in enumerate(surface.points):
            if point.y > 0.90:
                position = cmds.pointPosition("{}.vtx[{}]".format(self.copy, i), world=True)
                cmds.xform("{}.vtx[{}]".format(self.copy, i), worldSpace=True,
                           translation=(position[0] * 2.5, position[1], position[2] * 2.5))
        result = self.compare()
        self.assertGreaterEqual(result.score, 80)
        self.assertLess(result.score, 99)
        self.assertIn("Head", result.differing)

    def test_sphere_and_cube_are_dissimilar(self):
        for mesh in (cmds.polySphere()[0], cmds.polyCube()[0]):
            result = self.compare(mesh)
            self.assertLess(result.score, 80)
            self.assertFalse(result.matches)

    def test_different_topology_uses_symmetric_closest_surface(self):
        cmds.polySubdivideFacet(self.copy, divisions=1, constructionHistory=False)
        result = self.compare()
        self.assertGreater(result.score, 99)

    def test_rest_pose_restores_animation_time_connections_and_undo(self):
        head = self.demo.destination_joints["head_JNT"]
        cmds.setKeyframe(head, attribute="rotateZ", time=1, value=0)
        cmds.setKeyframe(head, attribute="rotateZ", time=24, value=60)
        cmds.currentTime(24)
        before = cmds.getAttr(head + ".rotateZ")
        inputs = cmds.listConnections(head, source=True, type="animCurve")
        cmds.undoInfo(state=True, infinity=True)
        cmds.createNode("transform", name="artist_last_action")
        result = self.compare()
        self.assertGreater(result.score, 99)
        self.assertEqual(cmds.currentTime(query=True), 24)
        self.assertEqual(cmds.getAttr(head + ".rotateZ"), before)
        self.assertEqual(cmds.listConnections(head, source=True, type="animCurve"), inputs)
        cmds.undo()
        self.assertFalse(cmds.objExists("artist_last_action"))

    def assert_weights(self, fit):
        source_skin = cmds.ls(cmds.listHistory(self.source), type="skinCluster")[0]
        source = skin_function(source_skin)
        target = skin_function(fit.skin_clusters[0])
        source_shape = surfaces([self.source])[0][0].info.shape
        target_shape = surfaces([self.copy])[0][0].info.shape
        count = cmds.polyEvaluate(self.source, vertex=True)
        original, nsrc = source.getWeights(dag_path(source_shape), vertex_component(count))
        copied, ndst = target.getWeights(dag_path(target_shape), vertex_component(count))
        src_columns = {p.fullPathName(): i for i, p in enumerate(source.influenceObjects())}
        dst_columns = {p.fullPathName(): i for i, p in enumerate(target.influenceObjects())}
        error = 0
        for s, d in zip(fit.source_joints, fit.joints):
            s, d = dag_path(s).fullPathName(), dag_path(d).fullPathName()
            if s in src_columns:
                error = max(error, max(abs(original[v * nsrc + src_columns[s]] - copied[v * ndst + dst_columns[d]])
                                       for v in range(count)))
        self.assertLess(error, 1e-4)
        print("WEIGHT_COPY_MAX_ERROR", error)

    def test_exact_weights_duplicate_and_single_bind_undo_redo(self):
        fit = fit_skeleton(self.demo.destination_root, [self.copy], namespace="copy")
        cmds.undoInfo(state=True, infinity=True)
        bind_skeleton(fit, [self.copy])
        self.assert_weights(fit)
        cmds.undo()
        self.assertFalse(cmds.objExists(fit.skin_clusters[0]))
        self.assertTrue(cmds.objExists(fit.root))
        cmds.redo()
        self.assert_weights(fit)

    def test_exact_weights_shifted_scaled_copy_and_fitted_alignment(self):
        cmds.setAttr(self.copy + ".scale", 0.63, 0.63, 0.63)
        cmds.setAttr(self.copy + ".translate", 240, -10, 35)
        fit = fit_skeleton(self.demo.destination_root, [self.copy], namespace="copy")
        self.assertAlmostEqual(fit.scale, 0.63, delta=1e-5)
        for src, dst in zip(fit.source_joints, fit.joints):
            a = cmds.xform(src, query=True, worldSpace=True, translation=True)
            b = cmds.xform(dst, query=True, worldSpace=True, translation=True)
            for actual, expected in zip(b, [a[0] * .63 + 240, a[1] * .63 - 10, a[2] * .63 + 35]):
                self.assertAlmostEqual(actual, expected, delta=1e-4)
        bind_skeleton(fit, [self.copy])
        self.assert_weights(fit)

    def test_general_weight_copy_normalized_after_subdivision(self):
        cmds.polySubdivideFacet(self.copy, divisions=1, constructionHistory=False)
        cmds.setAttr(self.copy + ".scale", 1.2, 1.2, 1.2)
        cmds.setAttr(self.copy + ".translateX", 210)
        fit = fit_skeleton(self.demo.destination_root, [self.copy], namespace="general")
        bind_skeleton(fit, [self.copy])
        skin = skin_function(fit.skin_clusters[0])
        shape = surfaces([self.copy])[0][0].info.shape
        weights, count = skin.getWeights(dag_path(shape), vertex_component(cmds.polyEvaluate(self.copy, vertex=True)))
        for i in range(0, len(weights), count):
            self.assertAlmostEqual(sum(weights[i:i + count]), 1, delta=1e-5)
            self.assertGreaterEqual(min(weights[i:i + count]), 0)

    def test_barycentric_weights_follow_a_known_linear_field(self):
        from maya.api import OpenMaya as om
        fn = om.MFnMesh()
        fn.create([om.MPoint(-1, 0, 0), om.MPoint(1, 0, 0), om.MPoint(0, 2, 0)], [3], [0, 1, 2])
        source = cmds.listRelatives(fn.fullPathName(), parent=True, fullPath=True)[0]
        cmds.select(clear=True)
        root = cmds.joint(name="field_root", position=(-1, 0, 0))
        tip = cmds.joint(name="field_tip", position=(1, 2, 0))
        skin = cmds.skinCluster([root, tip], source, toSelectedBones=True)[0]
        for index, weight in enumerate((1.0, 0.0, 0.5)):
            cmds.skinPercent(skin, "{}.vtx[{}]".format(source, index),
                             transformValue=[(root, weight), (tip, 1 - weight)], normalize=True)
        target = cmds.duplicate(source)[0]
        cmds.polySubdivideFacet(target, divisions=1, constructionHistory=False)
        for axis in "XYZ":
            cmds.setAttr(target + ".scale" + axis, lock=False)
            cmds.setAttr(target + ".translate" + axis, lock=False)
        cmds.setAttr(target + ".scale", 1.7, 1.7, 1.7)
        cmds.setAttr(target + ".translateX", 50)
        fit = fit_skeleton(root, [target], namespace="field")
        bind_skeleton(fit, [target])
        copied_root = dict(zip(fit.source_joints, fit.joints))[root]
        for index in range(cmds.polyEvaluate(target, vertex=True)):
            x = (cmds.pointPosition("{}.vtx[{}]".format(target, index), world=True)[0] - 50) / 1.7
            actual = cmds.skinPercent(fit.skin_clusters[0], "{}.vtx[{}]".format(target, index),
                                      query=True, transform=copied_root)
            self.assertAlmostEqual(actual, .5 - x / 2, delta=1e-4)

    def test_bind_requires_source_skin(self):
        fit = fit_skeleton(self.demo.source_root, [self.copy])
        with self.assertRaises(SceneError) as error:
            bind_skeleton(fit, [self.copy])
        self.assertTrue(error.exception.hint)
        self.assertFalse(cmds.ls(cmds.listHistory(self.copy), type="skinCluster"))
