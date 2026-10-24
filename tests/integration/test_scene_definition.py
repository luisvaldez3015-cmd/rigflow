"""Definition isolation uses scene joints/meshes, without helpers or Orig shapes."""
import unittest
from maya import cmds
from rigflow.core.errors import UnsupportedError
from rigflow.scene.viewport import DefinitionViewport, definition_nodes, main_model_panel


class SceneDefinitionTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)

    def test_isolate_nodes_expand_hierarchy_without_controls_or_intermediates(self):
        root = cmds.joint(name="Hips")
        child = cmds.joint(name="Spine", position=(0, 10, 0))
        mesh = cmds.polyCube(name="body")[0]
        cmds.parent(mesh, root)
        control = cmds.circle(name="control")[0]
        cmds.parent(control, root)
        orig = cmds.polyCube(name="intermediate")[0]
        cmds.parent(orig, root)
        shape = cmds.listRelatives(orig, shapes=True, fullPath=True)[0]
        cmds.setAttr(shape + ".intermediateObject", True)
        isolated = definition_nodes([root, mesh])
        expected = cmds.ls([root, child, mesh], long=True)
        self.assertEqual(set(isolated), set(expected))
        self.assertEqual(len(isolated), 3)
        self.assertTrue(cmds.getAttr(mesh + ".visibility"))
        self.assertEqual(definition_nodes([]), [])

    def test_definition_requires_interactive_maya(self):
        with self.assertRaises(UnsupportedError):
            DefinitionViewport.capture()
        with self.assertRaises(UnsupportedError):
            main_model_panel()

    def test_two_models_isolate_only_the_requested_model(self):
        a = cmds.polySphere(name="modelA")[0]
        b = cmds.polySphere(name="modelB")[0]
        self.assertEqual(definition_nodes([a]), cmds.ls(a, long=True))
        self.assertNotIn(cmds.ls(b, long=True)[0], definition_nodes([a]))
