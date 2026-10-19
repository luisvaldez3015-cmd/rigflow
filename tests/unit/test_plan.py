"""Rules that turn the models added in Setup into a proposed process."""
from __future__ import annotations

import unittest

from rigflow.core.character import AnimSlot, Character, MeshSlot, RigSlot, model_label
from rigflow.core.plan import PlanKind, derive_plan
from rigflow.core.session import Session, SessionEvent
from rigflow.mapping.matcher import label_skeleton
from tests.unit.fixtures import build as build_skeleton, custom_spec, mixamo_spec


def character(name, mesh=False, rig=False, anim=False, transferred=False, spec=None):
    """Compose a model with the requested slots; the rig is a real labelled skeleton."""
    model = Character(name)
    if mesh:
        model.mesh = MeshSlot(["{}_GEO".format(name)], 1200, skinned=rig)
    if rig:
        skeleton = build_skeleton(spec or mixamo_spec(), name=name)
        labeling = label_skeleton(skeleton)
        model.rig = RigSlot(skeleton.main_root(), skeleton, labeling, labeling.convention)
    if anim:
        model.anim = AnimSlot((1.0, 48.0), 24.0, animated_joints=20, transferred=transferred)
    return model


class CharacterTests(unittest.TestCase):
    def test_slots_and_contents(self):
        full = character("Hero", mesh=True, rig=True, anim=True)
        self.assertTrue(full.has_mesh and full.has_rig and full.has_anim)
        self.assertEqual(full.contents(), "mesh, rig and animation")
        self.assertEqual(character("Mocap", rig=True, anim=True).contents(), "rig and animation")
        self.assertEqual(character("Statue", mesh=True).contents(), "mesh only")
        self.assertEqual(character("Empty").contents(), "nothing usable")
        self.assertFalse(character("Empty").usable)
        self.assertTrue(full.rig.complete)
        self.assertEqual(full.anim.frame_count, 48)
        self.assertIn("Transferred by RigFlow", character("B", rig=True, anim=True, transferred=True).anim.describe())
        self.assertFalse(character("B", rig=True, anim=True, transferred=True).has_authored_anim)
        self.assertEqual(model_label(0), "Model A")
        self.assertEqual(model_label(1), "Model B")
        self.assertEqual(full.summary()["contents"], "mesh, rig and animation")

    def test_anim_slot_without_keyed_joints_is_not_animation(self):
        model = character("Hero", rig=True)
        model.anim = AnimSlot((1.0, 10.0), 24.0, animated_joints=0)
        self.assertFalse(model.has_anim)


class PlanTests(unittest.TestCase):
    def test_empty_and_single_model(self):
        self.assertEqual(derive_plan([]).kind, PlanKind.EMPTY)
        self.assertFalse(derive_plan([]).ready)
        plan = derive_plan([character("Hero", mesh=True, rig=True, anim=True)])
        self.assertEqual(plan.kind, PlanKind.NEED_SECOND)
        self.assertIn("Model A (Hero) has mesh, rig and animation, 48 frames.", plan.message)
        self.assertIn("receive", plan.message)
        self.assertIn("Mixamo", derive_plan([character("Nova", mesh=True, rig=True)]).message)
        self.assertIn("rigged or animated", derive_plan([character("Statue", mesh=True)]).message)
        self.assertEqual(plan.steps, ["Setup"])
        self.assertIsNone(plan.first_step)

    def test_animated_source_to_rigged_destination(self):
        source = character("Mixamo_Jump", rig=True, anim=True)
        destination = character("Nova", mesh=True, rig=True, spec=custom_spec())
        plan = derive_plan([destination, source])
        self.assertEqual(plan.kind, PlanKind.ANIMATION)
        self.assertEqual((plan.source_id, plan.destination_id), (source.character_id, destination.character_id))
        self.assertEqual(plan.title, "Transfer animation · Model B → Model A")
        self.assertIn("Model B is joints only (mocap).", plan.message)
        self.assertEqual(plan.steps, ["Setup", "Match", "Transfer"])
        self.assertEqual(plan.first_step, "match")
        self.assertEqual(plan.action_label, "Start: Match ›")
        self.assertTrue(plan.ready and plan.transfers_animation)
        self.assertFalse(plan.can_swap)

    def test_joints_only_destination_is_allowed(self):
        plan = derive_plan([character("A", rig=True, anim=True), character("B", rig=True, spec=custom_spec())])
        self.assertEqual(plan.kind, PlanKind.ANIMATION)
        self.assertIn("Model B is joints only", plan.message)

    def test_mesh_only_destination_needs_rig_first(self):
        source = character("Hero", mesh=True, rig=True, anim=True)
        plan = derive_plan([source, character("Statue", mesh=True)])
        self.assertEqual(plan.kind, PlanKind.RIG_THEN_ANIMATION)
        self.assertEqual(plan.steps, ["Setup", "Rig", "Match", "Transfer"])
        self.assertEqual(plan.first_step, "rig")
        self.assertEqual(plan.action_label, "Start: Rig ›")
        self.assertIn("copy Model A's skeleton", plan.message)
        self.assertTrue(plan.transfers_animation)

    def test_rig_only_when_nothing_is_animated(self):
        rigged = character("Nova", mesh=True, rig=True)
        plan = derive_plan([character("Statue", mesh=True), rigged])
        self.assertEqual(plan.kind, PlanKind.RIG)
        self.assertEqual(plan.source_id, rigged.character_id)
        self.assertEqual(plan.steps, ["Setup", "Rig"])
        self.assertFalse(plan.transfers_animation)
        self.assertTrue(plan.ready)

    def test_nothing_to_transfer_cases(self):
        plan = derive_plan([character("A", mesh=True, rig=True), character("B", mesh=True, rig=True, spec=custom_spec())])
        self.assertEqual(plan.kind, PlanKind.NOTHING)
        self.assertIn("Neither model is animated.", plan.issues)
        plan = derive_plan([character("A", rig=True, anim=True), character("B")])
        self.assertEqual(plan.kind, PlanKind.NOTHING)
        self.assertIn("Model B has neither a mesh nor a rig.", plan.issues)
        self.assertFalse(plan.ready)

    def test_both_animated_defaults_to_a_and_can_swap(self):
        a = character("A", mesh=True, rig=True, anim=True)
        b = character("B", mesh=True, rig=True, anim=True, spec=custom_spec())
        plan = derive_plan([a, b])
        self.assertEqual(plan.kind, PlanKind.ANIMATION)
        self.assertEqual(plan.source_id, a.character_id)
        self.assertTrue(plan.can_swap)
        self.assertTrue(any("Swap" in issue for issue in plan.issues))
        self.assertIn("already has animation", plan.message)
        swapped = derive_plan([a, b], preferred_source_id=b.character_id)
        self.assertEqual((swapped.source_id, swapped.destination_id), (b.character_id, a.character_id))
        self.assertEqual(swapped.title, "Transfer animation · Model B → Model A")

    def test_transferred_animation_does_not_make_the_destination_a_source(self):
        a = character("Walk", rig=True, anim=True)
        b = character("Nova", mesh=True, rig=True, anim=True, transferred=True, spec=custom_spec())
        plan = derive_plan([b, a])
        self.assertEqual(plan.kind, PlanKind.ANIMATION)
        self.assertEqual(plan.source_id, a.character_id)
        self.assertEqual(plan.destination_id, b.character_id)
        self.assertNotIn("already has animation", plan.message)

    def test_third_model_is_reported(self):
        plan = derive_plan([character("A", rig=True, anim=True), character("B", mesh=True, rig=True, spec=custom_spec()),
                            character("C", mesh=True)])
        self.assertEqual(plan.kind, PlanKind.ANIMATION)
        self.assertTrue(any("Only Model A and Model B" in issue for issue in plan.issues))


class SessionCharacterTests(unittest.TestCase):
    def test_session_tracks_models_labels_and_plan_events(self):
        session = Session()
        events = []
        session.subscribe(lambda event, payload: events.append(event))
        self.assertEqual(session.plan.kind, PlanKind.EMPTY)
        a = session.add_character(character("Walk", rig=True, anim=True))
        self.assertEqual(session.plan.kind, PlanKind.NEED_SECOND)
        self.assertEqual(events[-2:], [SessionEvent.CHARACTERS_CHANGED, SessionEvent.PLAN_CHANGED])
        b = session.add_character(character("Nova", mesh=True, rig=True, spec=custom_spec()))
        self.assertEqual(session.plan.kind, PlanKind.ANIMATION)
        self.assertIs(session.source, a)
        self.assertIs(session.destination, b)
        self.assertEqual(session.label_for(a.character_id), "Model A")
        self.assertEqual(session.label_for(b.character_id), "Model B")
        self.assertEqual(session.label_for("missing"), "Model")
        # Replacing keeps the position and the id.
        replacement = character("Run", rig=True, anim=True)
        session.replace_character(a.character_id, replacement)
        self.assertEqual(session.characters[0].name, "Run")
        self.assertEqual(session.characters[0].character_id, a.character_id)
        # Swapping only has an effect when both are animated.
        session.swap_direction()
        self.assertEqual(session.plan.source_id, a.character_id)
        b.anim = AnimSlot((1.0, 10.0), 24.0, animated_joints=5)
        session.character_updated(b.character_id)
        self.assertEqual(session.plan.source_id, b.character_id)
        self.assertEqual(session.plan.destination_id, a.character_id)
        session.remove_character(b.character_id)
        self.assertIsNone(session.preferred_source_id)
        self.assertEqual(session.plan.kind, PlanKind.NEED_SECOND)
        self.assertIsNone(session.remove_character("missing"))


if __name__ == "__main__":
    unittest.main()
