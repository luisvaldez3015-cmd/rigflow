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
        self.controller.add_model_from_file("hero.ma")
        self.controller.add_model_from_selection()
        result = self.controller.start_plan()
        return self.controller.session.get_clip(result["clip_id"])

    def test_full_workflow_manual_review_and_transfer(self):
        from rigflow.animation.clip import ClipStatus
        from rigflow.mapping.model import MatchStatus
        self.assertEqual(self.window.stack.count(), 4)
        self.assertEqual(self.window.stepper.current_step, 1)
        self.assertTrue(self.window.setup_view.add_tile.isVisible())
        self.assertEqual(self.window.setup_view.add_tile.size(), QtCore.QSize(112, 112))
        self.assertEqual(len(self.window.setup_view.model_cards), 0)
        source = self.controller.add_model_from_file("mixamorig.fbx")
        self.app.processEvents()
        self.assertTrue(self.window.setup_view.small_add_tile.isVisible())
        self.assertEqual(self.window.setup_view.second_label.text(), "Add the second model")
        self.assertEqual(len(self.window.setup_view.model_cards), 1)
        card = self.window.setup_view.model_cards[0]
        self.assertEqual(set(card.slots), {"Mesh", "Rig", "Anim"})
        self.assertEqual(card.slots["Mesh"].badge.label.text(), "None")
        self.assertEqual(card.slots["Anim"].badge.label.text(), "✓ Detected")
        target = self.controller.add_model_from_selection()
        self.app.processEvents()
        banner = self.window.setup_view.plan_banner
        self.assertIn("Transfer animation", banner.animation_card.title_label.text())
        self.assertEqual(banner.start_button.text(), "Start Match")
        self.assertTrue(banner.isVisible())
        banner.start_button.click()
        clip = self.controller.session.active_clip
        self.assertEqual(self.controller.session.source, source)
        self.assertEqual(self.controller.session.destination, target)
        self.assertEqual(len(self.window.stepper.buttons), 3)
        self.assertFalse(self.window.setup_view.add_tile.isVisible())
        self.assertTrue(self.window.validate_active().ok)
        self.window.open_match(clip.clip_id)
        view = self.window.match_view
        self.app.processEvents()
        self.assertIn("15/15", view.model_buttons["source"].text())
        self.assertEqual(self.window.stepper.current_step, 2)
        self.assertTrue(view.timer.isActive())
        self.assertFalse(self.window.statusBar().isVisible())
        self.assertFalse(hasattr(view, "details"))
        view.clear_slot("LeftHand")
        self.controller.selection = ["mixamorig:LeftHand"]
        view.click_slot("LeftHand")
        self.assertTrue(clip.mapping.matches["LeftHand"].manual)
        self.assertEqual(clip.mapping.matches["LeftHand"].status, MatchStatus.GREEN)
        self.assertEqual(view.body_map.states["LeftHand"], "assigned")
        self.assertTrue(view.review_button.isEnabled())
        self.window.open_transfer(clip.clip_id)
        self.assertEqual(self.window.stepper.current_step, 3)
        self.assertFalse(view.timer.isActive())
        self.assertIs(self.window.stack.currentWidget(), self.window.transfer_view)
        self.assertTrue(self.window.statusBar().isVisible())
        self.window.transfer_view._set_frame(23.5)
        self.assertEqual(self.controller.current_frame(), 23.5)
        with mock.patch.object(self.controller, "bake", wraps=self.controller.bake) as bake:
            self.window.transfer_view.transfer_button.click()
            bake.assert_called_once_with(clip.clip_id, to_layer=True)
        self.assertEqual(clip.status, ClipStatus.TRANSFERRED)
        self.assertTrue(target.anim.transferred)
        self.assertIs(self.controller.session.destination, target)
        self.assertTrue(self.window.transfer_view.result_card.isVisible())
        self.window.transfer_view.done_button.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.setup_view)
        self.assertEqual(self.window.stepper.current_step, 1)
        self.assertEqual(len(self.controller.session.clips), 1)
        self.assertFalse(self.controller.is_playing())

    def test_validate_missing_state_and_manual_unmatch(self):
        self.assertIsNone(self.window.validate_active())
        self.assertIn("Add an animation first", self.window.setup_view.validation_label.text())
        clip = self.controller.add_animation_from_file("walk.fbx")
        self.assertFalse(self.window.validate_active().ok)
        self.controller.set_rig_from_selection()
        self.window.validate_active()
        self.window.open_match(clip.clip_id)
        view = self.window.match_view
        # Required unmatched roles block Transfer; automatic reset restores them.
        view.set_side("destination")
        view.clear_slot("Hips")
        self.assertIsNone(clip.mapping.matches["Hips"].destination)
        self.assertFalse(view.review_button.isEnabled())
        self.controller.clear_manual(clip.clip_id)
        self.assertTrue(view.review_button.isEnabled())

        self.window.show_setup()
        self.assertFalse(view.timer.isActive())
        self.assertFalse(self.controller.definition_view_active)

    def test_new_animation_replaces_source_and_retains_destination(self):
        clip = self.populated_clip()
        source = self.controller.session.source
        target = self.controller.session.destination
        self.window.open_transfer(clip.clip_id)
        self.window.transfer_view.transfer_button.click()
        with mock.patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=("jump.fbx", "")):
            self.window.transfer_view.new_button.click()
        self.app.processEvents()
        self.assertIs(self.window.stack.currentWidget(), self.window.setup_view)
        self.assertEqual(self.controller.session.source.name, "jump")
        self.assertEqual(self.controller.session.source.character_id, source.character_id)
        self.assertIs(self.controller.session.destination, target)
        self.assertTrue(target.anim.transferred)
        self.assertIsNone(self.controller.session.get_clip(clip.clip_id))
        self.assertIsNone(self.controller._preview_id)
        self.assertEqual(len(self.controller.session.characters), 2)

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

    def test_mesh_only_destination_fit_refit_cancel_and_bind(self):
        self.controller.add_model_from_file("hero.ma")
        target = self.controller.add_model_from_file("same.obj")
        self.assertEqual(self.controller.session.plan.kind, "rig_then_animation")
        self.assertEqual(self.window.setup_view.plan_banner.start_button.text(), "Start Rig")
        self.assertEqual(len(self.window.stepper.buttons), 4)
        self.window.start_plan()
        self.assertIs(self.window.stack.currentWidget(), self.window.rig_view)
        self.assertEqual(self.window.stepper.current_step, 2)
        first = self.controller.rig_fit()
        self.assertIn(first.root, self.window.rig_view.viewport.isolate)
        self.window.rig_view.refit_button.click()
        self.assertIsNot(first, self.controller.rig_fit())
        self.window.rig_view.back_button.click()
        self.assertIsNone(self.controller.rig_fit())
        self.assertEqual(self.controller.session.plan.kind, "rig_then_animation")
        self.window.start_plan()
        self.window.rig_view.bind_button.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.match_view)
        self.assertTrue(target.has_rig)
        self.assertTrue(target.mesh.skinned)
        self.assertEqual(self.controller.session.plan.kind, "animation")
        self.assertEqual(len(self.window.stepper.buttons), 4)
        self.assertTrue(self.controller.validate(self.controller.session.active_clip_id).ok)

    def test_process_cards_similarity_replacement_and_blocked_actions(self):
        source = self.controller.add_model_from_file("hero.ma")
        target = self.controller.add_model_from_file("same_head.obj")
        banner = self.window.setup_view.plan_banner
        self.assertTrue(all(card.isVisible() for card in banner.cards))
        self.assertEqual(banner.rig_card.similarity_label.text(), "Mesh similarity 96%")
        self.assertEqual(banner.rig_card.differing_label.text(), "Differs around: Head")
        self.assertTrue(banner.rig_card.start_button.isEnabled())
        self.assertFalse(banner.animation_card.start_button.isEnabled())
        self.assertIn("use Transfer rig", banner.animation_card.reason_label.text())
        cached = self.controller.mesh_similarity(source, target)
        self.assertIs(cached, self.controller.mesh_similarity(source, target))
        for card in self.window.setup_view.model_cards:
            self.assertFalse(any(hasattr(tile, "detail") for tile in card.slots.values()))
        target = self.controller.replace_model_from_file(target.character_id, "other.obj")
        self.assertEqual(banner.rig_card.similarity_label.text(), "Mesh similarity 41%")
        self.assertFalse(banner.rig_card.start_button.isEnabled())
        self.assertIn("can't be transferred", banner.rig_card.reason_label.text())
        from rigflow.core.plan import PlanKind
        self.assertIsNone(self.controller.start_plan(PlanKind.RIG))
        self.assertIsNone(self.controller.start_plan(PlanKind.ANIMATION))
        self.assertIsNone(self.controller.rig_fit())
        self.assertIsNot(cached, self.controller.mesh_similarity(source, target))

    def test_rig_only_bind_returns_to_setup(self):
        self.controller.add_model_from_file("Nova.ma")
        target = self.controller.add_model_from_file("mesh.obj")
        self.assertEqual(self.controller.session.plan.kind, "rig")
        self.assertEqual(len(self.window.stepper.buttons), 2)
        self.window.start_plan()
        self.window.rig_view.bind_button.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.setup_view)
        self.assertTrue(target.has_rig)
        self.assertFalse(self.controller.session.clips)

    def test_removed_destination_resets_the_transferred_clip_state(self):
        from rigflow.animation.clip import ClipStatus
        clip = self.populated_clip()
        self.window.open_transfer(clip.clip_id)
        self.window.transfer_view.transfer_button.click()
        self.assertEqual(clip.status, ClipStatus.TRANSFERRED)
        self.window.show_setup()
        self.controller.remove_model(self.controller.session.destination.character_id)
        self.assertEqual(clip.status, ClipStatus.IMPORTED)
        self.assertIsNone(clip.mapping)
        self.assertEqual(clip.result, {})
        self.controller.add_model_from_file("same.obj")
        self.window.start_plan()
        self.assertIs(self.window.stack.currentWidget(), self.window.rig_view)
        texts = [button.text() for button in self.window.stepper.buttons]
        self.assertEqual(texts, ["✓ Setup", "2 Rig", "3 Match", "4 Transfer"])

    def test_changing_destination_discards_old_manual_joint_names(self):
        clip = self.populated_clip()
        match = clip.mapping.matches["LeftHand"]
        self.controller.set_manual_match(clip.clip_id, "LeftHand", match.source, match.destination)
        self.controller.start_plan()
        self.assertTrue(clip.mapping.matches["LeftHand"].manual)
        target = self.controller.session.destination
        self.controller.remove_model(target.character_id)
        self.controller.add_model_from_file("same.obj")
        self.window.start_plan()
        self.window.rig_view.bind_button.click()
        self.assertIs(self.controller.session.active_clip, clip)
        self.assertFalse(clip.mapping.matches["LeftHand"].manual)
        self.assertTrue(self.controller.validate(clip.clip_id).ok)

    def test_swap_reuse_remove_replace_and_viewport_labels(self):
        a = self.controller.add_model_from_file("walk.fbx")
        b = self.controller.add_model_from_file("hero.ma")
        banner = self.window.setup_view.plan_banner
        self.assertTrue(banner.swap_button.isVisible())
        self.window.start_plan()
        first_id = self.controller.session.active_clip_id
        self.window.show_setup()
        self.window.start_plan()
        self.assertEqual(self.controller.session.active_clip_id, first_id)
        self.assertEqual(len(self.controller.session.clips), 1)
        self.window.show_setup()
        banner.swap_button.click()
        self.assertIs(self.controller.session.source, b)
        self.window.start_plan()
        self.assertEqual(self.window.match_view.model_buttons["source"].text(), "Model B  15/15")
        self.assertEqual(self.window.match_view.model_buttons["destination"].text(), "Model A  15/15")
        self.assertEqual(len(self.controller.session.clips), 2)
        self.window.show_setup()
        replacement = self.controller.replace_model_from_file(a.character_id, "Nova.ma")
        self.assertEqual(replacement.character_id, a.character_id)
        self.assertEqual(self.controller.session.characters[0], replacement)
        self.assertIsNone(self.controller.session.get_clip(first_id))
        self.window.start_plan()
        self.window.open_transfer(self.controller.session.active_clip_id)
        self.controller.remove_model(b.character_id)
        self.assertIsNone(self.controller._preview_id)
        self.assertIs(self.window.stack.currentWidget(), self.window.setup_view)
        self.assertEqual(len(self.window.setup_view.model_cards), 1)
        self.assertIsNone(self.controller.session.rig)
        self.assertIsNone(self.controller.session.model)

    def test_obj_drop_acceptance_and_add_menu(self):
        from rigflow.ui.qt import QtGui
        from rigflow.ui.widgets.drop_area import DropArea, FILE_FILTER
        self.assertTrue(DropArea.accepts("Statue.OBJ"))
        self.assertIn("*.obj", FILE_FILTER)
        self.assertEqual([a.text() for a in self.window.add_menu.actions()],
                         ["From file…", "Use Maya selection", "From scene…"])
        mime = QtCore.QMimeData()
        mime.setUrls([QtCore.QUrl.fromLocalFile("C:/Statue.obj")])
        drop = QtGui.QDropEvent(QtCore.QPointF(10, 10), QtCore.Qt.CopyAction, mime,
                               QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        self.window.setup_view.empty_area.dropEvent(drop)
        self.assertTrue(drop.isAccepted())
        self.assertTrue(self.controller.session.characters[0].has_mesh)
        self.assertFalse(self.controller.session.characters[0].has_rig)
        card = self.window.setup_view.model_cards[0]
        mime.setUrls([QtCore.QUrl.fromLocalFile("C:/walk.fbx")])
        drop = QtGui.QDropEvent(QtCore.QPointF(10, 10), QtCore.Qt.CopyAction, mime,
                               QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
        card.dropEvent(drop)
        self.assertEqual(len(self.controller.session.characters), 1)
        self.assertTrue(self.controller.session.characters[0].has_anim)

    def test_fake_file_detection_rules(self):
        for path, contents in (("mixamo.fbx", (False, True, True)),
                               ("walk.ma", (False, True, True)), ("hero.ma", (True, True, True)),
                               ("Statue.fbx", (True, False, False)), ("unknown.obj", (True, False, False)),
                               ("Nova.ma", (True, True, False))):
            character = self.controller._file_model(path)
            self.assertEqual((character.has_mesh, character.has_rig, character.has_anim), contents)

    def test_multiple_clips_replace_remove_and_reset(self):
        clip = self.populated_clip()
        second = self.controller.add_animation_from_scene("walk_cycle:Hips")
        self.assertEqual(len(self.controller.session.clips), 2)
        original = clip.mapping.matches["Hips"]
        self.controller.set_manual_match(clip.clip_id, "Hips", original.source, original.destination)
        self.controller.auto_map(clip.clip_id)
        self.assertTrue(clip.mapping.matches["Hips"].manual)
        self.controller.clear_manual(clip.clip_id, "Hips")
        self.assertFalse(clip.mapping.matches["Hips"].manual)
        replacement = self.controller.replace_animation(second.clip_id, "jump.fbx")
        self.assertEqual(replacement.clip_id, second.clip_id)
        self.assertEqual(len(self.controller.session.clips), 2)
        self.controller.remove_clip(clip.clip_id)
        self.assertEqual(len(self.controller.session.clips), 1)

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

    def test_preset_roundtrip_and_slot_tooltips(self):
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
        body = self.window.matching_view.body_map
        self.assertEqual(body.joints["LeftHand"], "mixamorig:LeftHand")
        self.assertEqual(body.role_at(body.slot_position("LeftHand")), "LeftHand")

    def test_definition_art_layout_hit_testing_and_offscreen_paint(self):
        from rigflow.ui.widgets.body_map import BODY_SLOTS, BodyMap, hand_slots

        body = BodyMap()
        body.resize(800, 512)
        body.states = {role: "assigned" for role in BODY_SLOTS}
        body.show()
        self.app.processEvents()
        self.assertTrue(all(body.role_at(body.slot_position(role)) == role for role in BODY_SLOTS))
        self.assertFalse(body.grab().isNull())
        body.set_hands(True)
        body.states = {role: "assigned" for role in hand_slots()}
        self.app.processEvents()
        self.assertTrue(all(body.role_at(body.slot_position(role)) == role for role in hand_slots()))
        self.assertFalse(body.grab().isNull())
        body.waiting = "LeftHandMiddle2"
        body.states["LeftHandMiddle2"] = "waiting"
        body.states["RightHand"] = "invalid"
        body.states["LeftHandIndex3"] = "required"
        self.assertFalse(body.grab().isNull())
        body.close()

    def test_definition_slot_first_wrong_model_cancel_and_joint_first(self):
        from PySide2.QtTest import QTest
        clip = self.populated_clip()
        self.window.open_match(clip.clip_id)
        view = self.window.match_view
        view.clear_slot("LeftHand")
        self.controller.selection = []
        QTest.mouseClick(view.body_map, QtCore.Qt.LeftButton, pos=view.body_map.slot_position("LeftHand"))
        self.assertEqual(view.waiting, "LeftHand")
        self.assertEqual(view.body_map.waiting, "LeftHand")
        self.controller.selection = ["l_wrist_JNT"]
        view.poll_selection()
        self.assertEqual(view.waiting, "LeftHand")
        self.assertIn("belongs to Model B", view.status_line.text())
        self.controller.selection = ["mixamorig:LeftHand", "mixamorig:RightHand"]
        view.poll_selection()
        self.assertIsNone(clip.mapping.matches["LeftHand"].source)
        self.controller.selection = ["mixamorig:LeftHand"]
        view.poll_selection()
        self.assertEqual(clip.mapping.matches["LeftHand"].source, "mixamorig:LeftHand")
        self.assertIsNone(view.waiting)
        self.controller.selection = []
        view.click_slot("LeftHand")
        self.assertEqual(self.controller.selection, ["mixamorig:LeftHand"])
        view.clear_slot("LeftHand")
        self.controller.selection = []
        view.click_slot("LeftHand")
        view.click_slot("LeftHand")
        self.assertIsNone(view.waiting)
        view.click_slot("LeftHand")
        QTest.keyClick(view, QtCore.Qt.Key_Escape)
        self.assertIsNone(view.waiting)
        self.controller.selection = ["mixamorig:LeftHand"]
        view.click_slot("LeftHand")
        self.assertEqual(clip.mapping.matches["LeftHand"].source, "mixamorig:LeftHand")
        self.assertTrue(view.review_button.isEnabled())

        def clear_from_context_menu():
            menu = self.app.activePopupWidget()
            self.assertEqual([a.text() for a in menu.actions()], ["Clear", "Select in scene"])
            menu.actions()[0].trigger()
            menu.close()
        QtCore.QTimer.singleShot(0, clear_from_context_menu)
        QTest.mouseClick(view.body_map, QtCore.Qt.RightButton, pos=view.body_map.slot_position("LeftHand"))
        self.assertIsNone(clip.mapping.matches["LeftHand"].source)

    def test_definition_moves_clear_confirm_presets_and_lifetime(self):
        clip = self.populated_clip()
        self.window.open_match(clip.clip_id)
        view = self.window.match_view
        self.controller.selection = ["mixamorig:LeftHand"]
        view.click_slot("RightHand")
        self.assertIsNone(clip.mapping.matches["LeftHand"].source)
        self.assertIn("Moved", view.status_line.text())
        self.assertFalse(view.review_button.isEnabled())
        view.set_side("destination")
        view.display_buttons["Bones"].click()
        self.assertEqual(self.controller.definition_calls[-1], ("show", clip.clip_id, "destination", "Bones"))
        with mock.patch.object(QtWidgets.QMessageBox, "question", return_value=QtWidgets.QMessageBox.No):
            view.clear_button.click()
        self.assertEqual(clip.mapping.matches["Hips"].destination, "pelvis_JNT")
        with mock.patch.object(QtWidgets.QMessageBox, "question", return_value=QtWidgets.QMessageBox.Yes):
            view.clear_button.click()
        self.assertTrue(all(not m.destination for m in clip.mapping.matches.values()))
        view.auto_button.click()
        self.assertEqual(clip.mapping.matches["Hips"].destination, "pelvis_JNT")
        self.assertEqual([a.text() for a in view.preset_menu.actions()], ["Load preset…", "Save preset…"])
        view.map_tabs.setCurrentIndex(1)
        self.assertEqual(len(view.body_map.slots), 32)
        self.assertEqual(view.body_map.role_at(view.body_map.slot_position("LeftHandThumb3")), "LeftHandThumb3")
        self.window.show_setup()
        self.assertEqual(self.controller.definition_calls[-1], ("restore",))
        restores = self.controller.definition_calls.count(("restore",))
        view.deactivate()
        self.assertEqual(restores, self.controller.definition_calls.count(("restore",)))
        self.window.open_match(clip.clip_id)
        self.window.close()
        self.assertFalse(self.controller.definition_view_active)

    def test_missing_services_are_status_errors(self):
        from rigflow.ui.controller import Controller
        from rigflow.core.session import SessionEvent
        controller = Controller()
        events = []
        controller.session.subscribe(lambda event, payload: events.append((event, payload)))
        with mock.patch.object(controller, "_service", side_effect=ImportError("scene not installed")):
            self.assertIsNone(controller.set_model_from_selection())
            self.assertEqual(controller.list_scene_skeleton_roots(), [])
            self.assertIsNone(controller.add_model_from_file("walk.fbx"))
            self.assertIsNone(controller.add_model_from_selection())
            self.assertIsNone(controller.add_model_from_scene("root"))
            self.assertEqual(controller.list_scene_candidates(), [])
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
        result_type = make_dataclass("Result", [("backend", str), ("warnings", list),
                                                ("frame_range", tuple), ("baked_joints", list)])
        backend.bake.return_value = result_type("matrix", [], clip.frame_range, ["pelvis_JNT"])
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
            self.assertTrue(controller.session.destination.anim.transferred)
            self.assertEqual(controller.session.destination.anim.animated_joints, 1)
            self.assertEqual(controller._previews, {})
            self.assertIsNone(controller._playback_state)
            cmds.playbackOptions.assert_any_call(**old_state)
            cmds.currentTime.assert_any_call(72.5)
            backend.prepare.side_effect = RigFlowError("Unsupported rig", "Choose another backend")
            self.assertFalse(controller.start_preview(clip.clip_id))
            self.assertIsNone(controller._playback_state)
            self.assertGreaterEqual(backend.cleanup.call_count, 3)

    def test_real_model_import_start_replace_remove_contract(self):
        from rigflow.ui.controller import Controller
        from rigflow.ui.fake_controller import demo_skeleton
        controller = Controller()
        mesh = SimpleNamespace(transform="Nova_body", vertex_count=1200, skinned=True)
        source_scan = SimpleNamespace(name="walk", meshes=[], skeleton=SimpleNamespace(
            root="source:Hips", animated_joints=22), has_anim=True, frame_range=(4.0, 48.0),
            fps=24.0, warnings=["Joints only"])
        destination_scan = SimpleNamespace(name="Nova", meshes=[mesh], skeleton=SimpleNamespace(
            root="pelvis_JNT", animated_joints=0), has_anim=False, frame_range=None,
            fps=24.0, warnings=[])
        source_import = SimpleNamespace(path="walk.fbx", namespace="source", new_nodes=["source:Hips"])
        next_import = SimpleNamespace(path="jump.fbx", namespace="next", new_nodes=["next:Hips"])
        importer = SimpleNamespace(import_file=mock.Mock(return_value=source_import), remove_import=mock.Mock())
        characters = SimpleNamespace(scan_import=mock.Mock(return_value=source_scan),
                                      scan_nodes=mock.Mock(return_value=destination_scan))
        selected = ["Nova_body"]
        inspector = SimpleNamespace(selection=lambda: selected[:],
            find_skeleton_roots=lambda: ["source:Hips", "pelvis_JNT", "free:Hips", "rigflowHelper"],
            find_meshes=lambda: [mesh, SimpleNamespace(transform="unownedMesh")],
            _is_helper=lambda node: node == "rigflowHelper")
        services = dict(importer=importer, characters=characters, inspector=inspector,
            skeleton_reader=SimpleNamespace(read_skeleton_rest=lambda root: demo_skeleton(root == "source:Hips")),
            animation_io=SimpleNamespace(animation_range=lambda nodes: (4.0, 48.0), scene_fps=lambda: 24.0),
            undo=SimpleNamespace(undo_chunk=lambda name: nullcontext()))
        with mock.patch.object(controller, "_service", side_effect=lambda name: services[name]):
            a = controller.add_model_from_file("walk.fbx")
            self.assertTrue(a.has_rig and a.has_anim and not a.has_mesh)
            self.assertEqual(a.notes, ["Joints only"])
            self.assertEqual(a.namespace, "source")
            b = controller.add_model_from_selection()
            characters.scan_nodes.assert_called_once_with(["Nova_body"], "Nova_body")
            self.assertEqual(b.mesh.vertex_count, 1200)
            self.assertEqual(controller.list_scene_candidates(), ["free:Hips", "unownedMesh"])
            result = controller.start_plan()
            clip = controller.session.get_clip(result["clip_id"])
            self.assertEqual(result["step"], "match")
            self.assertEqual(clip.frame_range, (4.0, 48.0))
            self.assertEqual(controller.session.rig.root, "pelvis_JNT")
            self.assertEqual(controller.session.model.meshes, ["Nova_body"])
            self.assertEqual(controller.start_plan()["clip_id"], clip.clip_id)
            self.assertEqual(len(controller.session.clips), 1)
            importer.import_file.side_effect = RuntimeError("Broken import")
            with mock.patch("rigflow.ui.controller.LOG.exception"):
                self.assertIsNone(controller.replace_model_from_file(a.character_id, "broken.fbx"))
            self.assertIs(controller.session.source, a)
            self.assertIsNotNone(controller.session.get_clip(clip.clip_id))
            importer.import_file.side_effect = None
            importer.import_file.return_value = next_import
            replacement = controller.replace_model_from_file(a.character_id, "jump.fbx")
            self.assertEqual(replacement.character_id, a.character_id)
            self.assertEqual(controller.session.characters[0], replacement)
            self.assertIsNone(controller.session.get_clip(clip.clip_id))
            importer.remove_import.assert_called_once_with(source_import)
            controller.remove_model(replacement.character_id)
            importer.remove_import.assert_called_with(next_import)
            self.assertIsNone(controller.session.rig)
            self.assertIsNone(controller.session.model)
            self.assertFalse(controller.session.clips)
            selected[:] = []
            self.assertIsNone(controller.add_model_from_selection())

    def test_real_rig_fit_bind_services(self):
        from rigflow.ui.controller import Controller
        from rigflow.ui.fake_controller import demo_skeleton
        self.controller.add_model_from_file("hero.ma")
        target = self.controller.add_model_from_file("same.obj")
        controller = Controller(self.controller.session)
        fit = SimpleNamespace(root="Statue_Hips", joints=["Statue_Hips"], scale=0.7,
                              skin_clusters=[], warnings=[])
        transfer = SimpleNamespace(fit_skeleton=mock.Mock(return_value=fit),
            remove_fit=mock.Mock(), bind_skeleton=mock.Mock(return_value=fit))
        services = dict(undo=SimpleNamespace(undo_chunk=lambda name: nullcontext()),
            skeleton_reader=SimpleNamespace(read_skeleton_rest=lambda root: demo_skeleton(root != "Statue_Hips")),
            animation_io=SimpleNamespace(animation_range=lambda nodes: (1.0, 120.0), scene_fps=lambda: 24.0))
        with mock.patch.object(controller, "_service", side_effect=lambda name: services[name]), \
             mock.patch("rigflow.ui.controller.importlib.import_module", return_value=transfer):
            self.assertEqual(controller.start_plan(), {"step": "rig"})
            transfer.fit_skeleton.assert_called_once_with("mixamorig:Hips", target.mesh.meshes, namespace=None)
            self.assertEqual(controller.rig_viewport_nodes(), target.mesh.meshes + [fit.root])
            controller.refit_rig()
            transfer.remove_fit.assert_called_once_with(fit)
            result = controller.bind_rig()
            self.assertEqual(result["step"], "match")
            transfer.bind_skeleton.assert_called_once_with(fit, target.mesh.meshes)
            self.assertEqual(target.rig.root, fit.root)
            self.assertTrue(target.mesh.skinned)
            self.assertIsNone(controller.rig_fit())
            self.assertTrue(controller.validate(result["clip_id"]).ok)

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
