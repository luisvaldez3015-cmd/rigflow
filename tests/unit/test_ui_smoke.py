"""Headless UI workflow and controller failure-boundary regressions."""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import nullcontext
from dataclasses import make_dataclass
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from rigflow.ui.qt import QtCore, QtWidgets
except ImportError:
    QtWidgets = None


@unittest.skipIf(QtWidgets is None, "No PySide2/PySide6 binding installed")
class UISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        from rigflow.ui.fake_controller import FakeController
        from rigflow.ui.main_window import MainWindow
        self.controller = FakeController()
        self.window = MainWindow(self.controller)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)

    def populated_clip(self):
        self.controller.set_model_from_selection()
        self.controller.set_rig_from_selection()
        return self.controller.add_animation_from_file("walk_cycle.fbx")

    def test_full_workflow_manual_review_and_transfer(self):
        from rigflow.animation.clip import ClipStatus
        from rigflow.mapping.model import MatchStatus
        self.assertEqual(self.window.stack.count(), 3)
        self.assertEqual(self.window.stepper.current_step, 1)
        self.assertEqual(set(self.window.setup_view.slot_cards), {"Mesh", "Rig", "Anim"})
        self.assertIn("Mesh", self.window.model_section.title)
        self.assertIn("Rig", self.window.rig_section.title)
        self.assertIn("Anim", self.window.animation_section.title)
        self.assertTrue(self.window.setup_view.add_tile.isVisible())
        self.assertEqual(self.window.setup_view.add_tile.size(), QtCore.QSize(112, 112))
        self.assertEqual(self.window.clip_list.rowCount(), 0)
        clip = self.populated_clip()
        self.assertFalse(self.window.setup_view.add_tile.isVisible())
        self.assertTrue(self.window.setup_view.small_add_tile.isVisible())
        self.assertFalse(self.window.setup_view.next_button.isEnabled())
        self.assertTrue(self.window.validate_active().ok)
        self.assertTrue(self.window.setup_view.next_button.isEnabled())
        self.assertEqual(self.window.clip_list.rowCount(), 1)
        self.window.open_match(clip.clip_id)
        view = self.window.match_view
        self.app.processEvents()
        self.assertEqual(view.mapping_table.rowCount(), len(clip.mapping.sorted_matches()))
        self.assertEqual(self.window.stepper.current_step, 2)
        self.assertTrue(view.timer.isActive())
        self.assertTrue(view.details.isHidden())
        self.assertIn("mixamorig:LeftHand", view.source_selection.text())
        self.assertIn("l_wrist_JNT", view.destination_selection.text())
        view.match_button.click()
        self.assertTrue(clip.mapping.matches["LeftHand"].manual)
        self.assertEqual(clip.mapping.matches["LeftHand"].status, MatchStatus.GREEN)
        row = next(i for i, match in enumerate(view.mapping_table.matches) if match.role == "LeftHand")
        badge = view.mapping_table.cellWidget(row, 0)
        from rigflow.ui import theme
        self.assertEqual(badge.color.name(), theme.GREEN)
        self.assertTrue(view.review_button.isEnabled())
        self.window.open_transfer(clip.clip_id)
        self.assertEqual(self.window.stepper.current_step, 3)
        self.assertFalse(view.timer.isActive())
        self.assertIs(self.window.stack.currentWidget(), self.window.transfer_view)
        self.window.transfer_view._set_frame(23.5)
        self.assertEqual(self.controller.current_frame(), 23.5)
        with mock.patch.object(self.controller, "bake", wraps=self.controller.bake) as bake:
            self.window.transfer_view.transfer_button.click()
            bake.assert_called_once_with(clip.clip_id, to_layer=True)
        self.assertEqual(clip.status, ClipStatus.TRANSFERRED)
        self.assertTrue(self.window.transfer_view.result_card.isVisible())
        self.window.transfer_view.done_button.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.setup_view)
        self.assertEqual(self.window.stepper.current_step, 1)
        self.assertEqual(self.window.clip_list.rowCount(), 1)
        self.assertFalse(self.controller.is_playing())

    def test_validate_missing_state_and_manual_unmatch(self):
        self.assertIsNone(self.window.validate_active())
        self.assertIn("Add an animation first", self.window.setup_view.validation_label.text())
        clip = self.controller.add_animation_from_file("walk.fbx")
        self.assertFalse(self.window.validate_active().ok)
        self.assertFalse(self.window.setup_view.next_button.isEnabled())
        self.controller.set_rig_from_selection()
        self.window.validate_active()
        self.window.open_match(clip.clip_id)
        view = self.window.match_view
        # Required unmatched roles block Transfer; automatic reset restores them.
        self.controller.remember_selected(clip.clip_id, "mixamorig:Hips")
        self.controller.remember_selected(clip.clip_id, "pelvis_JNT", True)
        view.poll_selection()
        view.unmatch_button.click()
        self.assertIsNone(clip.mapping.matches["Hips"].destination)
        self.assertFalse(view.review_button.isEnabled())
        self.controller.clear_manual(clip.clip_id)
        self.assertTrue(view.review_button.isEnabled())
        self.window.show_setup()
        self.assertFalse(view.timer.isActive())
        self.assertEqual(self.controller.selected_pair(clip.clip_id), (None, None))

    def test_new_animation_retains_transfer_and_opens_add_menu(self):
        from rigflow.animation.clip import ClipStatus
        clip = self.populated_clip()
        self.window.open_transfer(clip.clip_id)
        self.window.transfer_view.transfer_button.click()
        self.window.transfer_view.new_button.click()
        self.app.processEvents()
        self.assertIs(self.window.stack.currentWidget(), self.window.setup_view)
        self.assertEqual(clip.status, ClipStatus.TRANSFERRED)
        self.assertIsNone(self.controller._preview_id)
        self.assertTrue(self.window.add_menu.isVisible())
        self.window.add_menu.close()

    def test_real_selection_remembers_each_side_and_tree_override(self):
        from rigflow.ui.controller import Controller
        clip = self.populated_clip()
        controller = Controller(self.controller.session)
        selection = ["|mixamorig:LeftHand"]
        inspector = SimpleNamespace(selection=lambda: selection[:])
        with mock.patch.object(controller, "_service", return_value=inspector):
            controller.begin_selection(clip.clip_id)
            self.assertEqual(controller.selected_pair(clip.clip_id), ("mixamorig:LeftHand", None))
            selection[:] = ["|l_wrist_JNT"]
            self.assertEqual(controller.selected_pair(clip.clip_id), ("mixamorig:LeftHand", "l_wrist_JNT"))
            controller.remember_selected(clip.clip_id, "mixamorig:RightHand")
            self.assertEqual(controller.selected_pair(clip.clip_id)[0], "mixamorig:RightHand")
            controller.clear_selected_pair(clip.clip_id)
            self.assertEqual(controller.selected_pair(clip.clip_id), (None, None))

    def test_multiple_clips_replace_remove_and_reset(self):
        clip = self.populated_clip()
        second = self.controller.add_animation_from_scene("walk_cycle:Hips")
        self.assertEqual(self.window.clip_list.rowCount(), 2)
        original = clip.mapping.matches["Hips"]
        self.controller.set_manual_match(clip.clip_id, "Hips", original.source, original.destination)
        self.controller.auto_map(clip.clip_id)
        self.assertTrue(clip.mapping.matches["Hips"].manual)
        self.controller.clear_manual(clip.clip_id, "Hips")
        self.assertFalse(clip.mapping.matches["Hips"].manual)
        replacement = self.controller.replace_animation(second.clip_id, "jump.fbx")
        self.assertEqual(replacement.clip_id, second.clip_id)
        self.assertEqual(self.window.clip_list.rowCount(), 2)
        self.controller.remove_clip(clip.clip_id)
        self.assertEqual(self.window.clip_list.rowCount(), 1)

    def test_validation_blocks_review_and_exclusion(self):
        clip = self.populated_clip()
        self.window.open_matching(clip.clip_id)
        self.controller.set_excluded(clip.clip_id, "Hips", True)
        self.assertFalse(self.controller.validate(clip.clip_id).ok)
        self.assertFalse(self.window.matching_view.review_button.isEnabled())
        self.window.open_review(clip.clip_id)
        self.assertIs(self.window.stack.currentWidget(), self.window.matching_view)
        self.assertIsNone(self.controller.bake(clip.clip_id))
        self.controller.set_excluded(clip.clip_id, "Hips", False)
        self.assertTrue(self.controller.validate(clip.clip_id).ok)

    def test_preset_roundtrip_and_joint_search(self):
        clip = self.populated_clip()
        match = clip.mapping.matches["Hips"]
        self.controller.set_manual_match(clip.clip_id, "Hips", match.source, match.destination)
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "mapping.rigflow.json")
            self.assertEqual(self.controller.save_preset(clip.clip_id, path), path)
            self.controller.clear_manual(clip.clip_id)
            report = self.controller.load_preset(clip.clip_id, path)
            self.assertTrue(report.ok)
            self.assertTrue(clip.mapping.matches["Hips"].manual)
        self.window.open_matching(clip.clip_id)
        tree = self.window.matching_view.source_tree
        tree.search.setText("LeftHand")
        self.assertFalse(tree.items["mixamorig:LeftHand"].isHidden())
        self.assertTrue(tree.items["mixamorig:RightFoot"].isHidden())

    def test_missing_services_are_status_errors(self):
        from rigflow.ui.controller import Controller
        from rigflow.core.session import SessionEvent
        controller = Controller()
        events = []
        controller.session.subscribe(lambda event, payload: events.append((event, payload)))
        with mock.patch.object(controller, "_service", side_effect=ImportError("scene not installed")):
            self.assertIsNone(controller.set_model_from_selection())
            self.assertEqual(controller.list_scene_skeleton_roots(), [])
        statuses = [payload for event, payload in events if event == SessionEvent.STATUS]
        self.assertEqual(statuses[-1]["level"], "error")
        self.assertIn("Service unavailable", statuses[-1]["message"])
        self.assertFalse(controller.validate("missing").ok)

    def test_close_releases_session_subscriptions_and_preview(self):
        clip = self.populated_clip()
        self.window.open_review(clip.clip_id)
        self.controller.play()
        self.window.close()
        self.assertFalse(self.controller.is_playing())
        self.assertIsNone(self.controller._preview_id)
        self.assertEqual(len(self.controller.session._listeners), 0)

    def test_real_controller_import_inspect_and_remove_contracts(self):
        from rigflow.ui.controller import Controller
        from rigflow.ui.fake_controller import demo_skeleton
        controller = Controller()
        mesh = SimpleNamespace(transform="body", vertex_count=1200, skinned=True)
        report = SimpleNamespace(meshes=[mesh], skeletons=[SimpleNamespace(root="source:Hips")])
        imported = SimpleNamespace(path="walk.fbx", namespace="source", report=report)
        inspector = SimpleNamespace(selection=lambda: ["body"], inspect_scene=lambda nodes: report,
                                    find_skeleton_roots=lambda nodes=None: ["destination:Hips"],
                                    skeleton_root_for_mesh=lambda item: "destination:Hips")
        importer = SimpleNamespace(import_file=mock.Mock(return_value=imported), remove_import=mock.Mock())
        reader = SimpleNamespace(read_skeleton_rest=lambda root: demo_skeleton(root == "source:Hips"))
        services = dict(inspector=inspector, importer=importer, skeleton_reader=reader,
                        animation_io=SimpleNamespace(animation_range=lambda nodes: (4.0, 48.0), scene_fps=lambda: 24.0),
                        undo=SimpleNamespace(undo_chunk=lambda name: nullcontext()))
        with mock.patch.object(controller, "_service", side_effect=lambda name: services[name]):
            self.assertTrue(controller.set_model_from_selection().valid)
            self.assertTrue(controller.set_rig_from_selection().valid)
            clip = controller.add_animation_from_file("walk.fbx")
            self.assertEqual(clip.frame_range, (4.0, 48.0))
            self.assertEqual(clip.namespace, "source")
            self.assertTrue(controller.validate(clip.clip_id).ok)
            self.assertEqual(len(controller.session.clips), 1)
            controller.remove_clip(clip.clip_id)
            importer.remove_import.assert_called_once_with(imported)
            self.assertEqual(len(controller.session.clips), 0)

    def test_real_preview_bake_restores_timeline_and_cleans_backend(self):
        from rigflow.ui.controller import Controller
        from rigflow.animation.clip import ClipStatus
        from rigflow.core.errors import RigFlowError
        clip = self.populated_clip()
        controller = Controller(self.controller.session)
        backend = mock.Mock()
        backend.name = "matrix"
        result_type = make_dataclass("Result", [("backend", str), ("warnings", list)])
        backend.bake.return_value = result_type("matrix", [])
        old_state = dict(minTime=-10, maxTime=200, animationStartTime=-20, animationEndTime=220, loop="once")
        cmds = mock.Mock()
        cmds.playbackOptions.side_effect = lambda **kw: old_state[next(k for k in kw if k != "query")] if kw.get("query") else None
        cmds.currentTime.return_value = 72.5
        services = dict(undo=SimpleNamespace(undo_chunk=lambda name: nullcontext()),
                        animation_io=SimpleNamespace(set_playback_range=mock.Mock()))
        modules = {"rigflow.retargeting.base": SimpleNamespace(RetargetRequest=lambda **kw: SimpleNamespace(**kw)),
                   "rigflow.retargeting": SimpleNamespace(get_retargeter=lambda: backend)}
        with mock.patch.object(controller, "_service", side_effect=lambda name: services[name]), \
             mock.patch.object(controller, "_cmds", return_value=cmds), \
             mock.patch("rigflow.ui.controller.importlib.import_module", side_effect=lambda name: modules[name]):
            self.assertTrue(controller.start_preview(clip.clip_id))
            self.assertIn("Source playback only", controller.preview_message(clip.clip_id))
            self.assertEqual(clip.status, ClipStatus.PREVIEWING)
            result = controller.bake(clip.clip_id, to_layer=False)
            self.assertEqual(result.backend, "matrix")
            self.assertFalse(backend.prepare.call_args[0][0].bake_to_layer)
            self.assertEqual(clip.status, ClipStatus.TRANSFERRED)
            self.assertEqual(controller._previews, {})
            self.assertIsNone(controller._playback_state)
            cmds.playbackOptions.assert_any_call(**old_state)
            cmds.currentTime.assert_any_call(72.5)
            backend.prepare.side_effect = RigFlowError("Unsupported rig", "Choose another backend")
            self.assertFalse(controller.start_preview(clip.clip_id))
            self.assertIsNone(controller._playback_state)
            self.assertGreaterEqual(backend.cleanup.call_count, 3)

    def test_singleton_and_dev_reload_launcher(self):
        # The fixture window is a valid singleton too, even with a FakeController.
        from rigflow.ui.launcher import show
        self.assertIs(show(), self.window)
        new_window = show(dev_reload=True)
        try:
            self.assertIsNot(new_window, self.window)
            self.assertIs(show(), new_window)
            self.assertFalse(new_window._disposed)
        finally:
            new_window.close()
            new_window.deleteLater()
        # dev_reload deleted the fixture's old C++ instance.
        from rigflow.ui.fake_controller import FakeController
        from rigflow.ui.main_window import MainWindow
        self.window = MainWindow(FakeController())

    def test_viewport_private_camera_cleanup_on_embedding_failure(self):
        from rigflow.ui.controller import Controller
        controller = Controller()
        viewport = mock.Mock()
        viewport.create_model_panel.return_value = "privatePanel"
        viewport.frame_nodes.side_effect = RuntimeError("Could not frame")
        cmds = mock.Mock()
        cmds.duplicate.return_value = ["privateCamera"]
        # Viewport furniture (panels, private cameras) must stay off the undo queue.
        services = {"viewport": viewport, "undo": SimpleNamespace(
            undo_chunk=lambda name: nullcontext(), suspended_undo=lambda: nullcontext())}
        with mock.patch("rigflow.ui.controller.compat.in_maya", return_value=True), \
             mock.patch("rigflow.ui.controller.compat.is_batch", return_value=False), \
             mock.patch.object(controller, "_service", side_effect=lambda name: services[name]), \
             mock.patch.object(controller, "_cmds", return_value=cmds), \
             mock.patch("rigflow.ui.controller.LOG.exception"):
            self.assertIsNone(controller.create_viewport("host", isolate=["Hips"]))
            viewport.delete_model_panel.assert_called_once_with("privatePanel")
            cmds.delete.assert_called_once_with("privateCamera")
            self.assertEqual(controller._viewport_cameras, {})
            viewport.frame_nodes.side_effect = None
            self.assertEqual(controller.create_viewport("host"), "privatePanel")
            self.assertEqual(controller._viewport_cameras, {"privatePanel": "privateCamera"})
            controller.delete_viewport("privatePanel")
            self.assertEqual(controller._viewport_cameras, {})


if __name__ == "__main__":
    unittest.main()
