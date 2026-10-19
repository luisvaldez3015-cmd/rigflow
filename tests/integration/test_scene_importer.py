"""Round-trip actual FBX/Maya files and verify isolated ownership cleanup."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from unittest import mock

from maya import cmds, mel

import scene_fixtures as sf
import fixtures
from rigflow.core.errors import ImportError_
from rigflow.scene import import_file, remove_import


class SceneImporterTests(unittest.TestCase):
    def setUp(self):
        sf.new_scene()
        self.directory = tempfile.mkdtemp(prefix="rigflow_scene_")

    def tearDown(self):
        sf.new_scene()
        shutil.rmtree(self.directory)

    def _export(self, extension, animated=True, mesh_only=False, camera_only=False):
        path = os.path.join(self.directory, "source clip." + extension)
        if mesh_only:
            root = cmds.polyCube()[0]
        elif camera_only:
            root = cmds.camera()[0]
        else:
            created = sf.build_skeleton(fixtures.mixamo_spec())
            root = created["mixamorig:Hips"]
            if animated:
                sf.animate_jump(created, sf.mixamo_roles())
        cmds.select(root, hierarchy=True)
        if extension == "fbx":
            cmds.loadPlugin("fbxmaya", quiet=True)
            # Keep the exporter deterministic without changing Maya's scene units.
            mel.eval("FBXExportBakeComplexAnimation -v false;")
            cmds.file(path, force=True, options="v=0;", type="FBX export", exportSelected=True)
        else:
            cmds.file(path, force=True, options="v=0;",
                      type="mayaAscii" if extension == "ma" else "mayaBinary", exportSelected=True)
        sf.new_scene()
        return path

    def _check_animated_import(self, path, kind):
        result = import_file(path)
        self.assertEqual(result.kind, kind)
        self.assertTrue(result.namespace.startswith("rigflow_src_"))
        self.assertTrue(result.report.has_skeleton)
        self.assertEqual(len(result.report.skeletons), 1)
        skeleton = result.report.skeletons[0]
        self.assertEqual(skeleton.joint_count, 65)
        self.assertTrue(all(n.startswith(result.namespace + ":") for n in skeleton.joints))
        self.assertTrue(result.report.has_animation)
        self.assertGreater(skeleton.animated_joints, 0)
        # FBX versions may shift the exported time origin by one frame.
        tolerance = 1 if kind == "fbx" else 0
        self.assertAlmostEqual(result.report.frame_range[0], 1, delta=tolerance)
        self.assertAlmostEqual(result.report.frame_range[1], 48, delta=tolerance)
        print("{} round trip: range={}, root={}, bindPose={}".format(
            kind, result.report.frame_range, skeleton.root, skeleton.has_bind_pose))
        self.assertTrue(result.new_nodes)
        remove_import(result)
        self.assertFalse(any(cmds.objExists(n) for n in result.new_nodes))
        self.assertFalse(cmds.namespace(exists=result.namespace))
        remove_import(result)

    def test_fbx_roundtrip(self):
        self._check_animated_import(self._export("fbx"), "fbx")

    def test_maya_ascii_roundtrip(self):
        self._check_animated_import(self._export("ma"), "maya")

    def test_maya_binary_roundtrip(self):
        self._check_animated_import(self._export("mb"), "maya")

    def test_obj_mesh_roundtrip(self):
        path = os.path.join(self.directory, "mesh only.obj")
        cube = cmds.polyCube()[0]
        cmds.select(cube)
        cmds.loadPlugin("objExport", quiet=True)
        cmds.file(path, force=True, type="OBJexport", exportSelected=True,
                  options="groups=1;ptgroups=1;materials=0;smoothing=1;normals=1")
        sf.new_scene()
        result = import_file(path)
        self.assertEqual(result.kind, "obj")
        self.assertEqual(len(result.report.meshes), 1)
        self.assertFalse(result.report.has_skeleton)
        self.assertEqual(result.report.meshes[0].vertex_count, 8)
        remove_import(result)
        self.assertFalse(any(cmds.objExists(n) for n in result.new_nodes))
        self.assertFalse(cmds.namespace(exists=result.namespace))

    def test_mesh_only_and_namespace_collisions(self):
        path = self._export("ma", mesh_only=True)
        first = import_file(path)
        second = import_file(path)
        self.assertEqual(second.namespace, first.namespace + "_1")
        self.assertTrue(first.report.has_mesh)
        self.assertFalse(first.report.has_skeleton)
        self.assertFalse(first.report.has_animation)
        cmds.namespace(add="userSpace")
        cmds.namespace(setNamespace=":userSpace")
        third = import_file(path, namespace="chosen namespace")
        self.assertEqual(third.namespace, "chosen_namespace")
        self.assertEqual(cmds.namespaceInfo(currentNamespace=True, absoluteName=True), ":userSpace")
        cmds.namespace(setNamespace=":")
        # Already-deleted members and repeated removal must be tolerated.
        cmds.delete(first.report.meshes[0].transform)
        remove_import(first)
        self.assertTrue(cmds.objExists(second.report.meshes[0].transform))
        remove_import(second)
        remove_import(third)

    def test_invalid_paths_and_empty_content(self):
        with self.assertRaises(ImportError_) as missing:
            import_file(os.path.join(self.directory, "missing.fbx"))
        self.assertTrue(missing.exception.hint)
        path = os.path.join(self.directory, "unsupported.txt")
        with open(path, "w") as stream:
            stream.write("not a scene")
        with self.assertRaises(ImportError_):
            import_file(path)
        path = self._export("ma", camera_only=True)
        before = set(cmds.ls(long=True))
        with self.assertRaisesRegex(ImportError_, "no joints or meshes"):
            import_file(path)
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertFalse(cmds.namespace(exists="rigflow_src_source_clip"))

    def test_failed_import_cleans_partial_nodes(self):
        path = self._export("ma", mesh_only=True)
        before = set(cmds.ls(long=True))
        original_file = cmds.file

        def broken_file(*args, **kwargs):
            if kwargs.get("i"):
                cmds.namespace(add=kwargs["namespace"])
                cmds.createNode("transform", name=kwargs["namespace"] + ":partial")
                raise RuntimeError("translator failure")
            return original_file(*args, **kwargs)

        with mock.patch("rigflow.scene.importer.cmds.file", side_effect=broken_file):
            with self.assertRaises(ImportError_):
                import_file(path)
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertFalse(cmds.namespace(exists="rigflow_src_source_clip"))

    def test_empty_file_does_not_claim_existing_content(self):
        path = os.path.join(self.directory, "empty.ma")
        cmds.file(rename=path)
        cmds.file(save=True, type="mayaAscii", force=True)
        sf.new_scene()
        cube = cmds.polyCube(name="destination")[0]
        before = set(cmds.ls(long=True))
        with self.assertRaisesRegex(ImportError_, "no joints or meshes"):
            import_file(path)
        self.assertTrue(cmds.objExists(cube))
        self.assertEqual(set(cmds.ls(long=True)), before)
        self.assertFalse(cmds.namespace(exists="rigflow_src_empty"))

    def test_fbx_mel_fallback(self):
        path = self._export("fbx")
        original_file = cmds.file

        def reject_translator(*args, **kwargs):
            if kwargs.get("i") and kwargs.get("type") == "FBX":
                raise RuntimeError("FBX translator route unavailable")
            return original_file(*args, **kwargs)

        with mock.patch("rigflow.scene.importer.cmds.file", side_effect=reject_translator):
            self._check_animated_import(path, "fbx")
