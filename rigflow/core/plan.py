"""Decide what RigFlow can do with the models added in Setup.

Given the models in order (Model A, Model B, ...) the plan says which one is
the **source**, which one is the **destination**, and which steps follow:

===================  =========================================================
``ANIMATION``        the source is animated and the destination has a rig:
                     Setup → Match → Transfer.
``RIG_THEN_ANIMATION`` the destination is a mesh without a rig: Setup → Rig
                     (copy and fit the source skeleton, bind) → Match → Transfer.
``RIG``              nothing is animated, but one model has a rig and the other
                     is a mesh only: Setup → Rig.
``NEED_SECOND``      only one model so far.
``EMPTY`` / ``NOTHING``  nothing to do (no models / nothing transferable).
===================  =========================================================

Pure Python, deterministic and fully unit tested; the UI only renders it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Sequence

from rigflow.core.character import Character, model_label


class PlanKind(str, Enum):
    EMPTY = "empty"
    NEED_SECOND = "need_second"
    ANIMATION = "animation"
    RIG_THEN_ANIMATION = "rig_then_animation"
    RIG = "rig"
    NOTHING = "nothing"


_STEPS = {
    PlanKind.ANIMATION: ("Setup", "Match", "Transfer"),
    PlanKind.RIG_THEN_ANIMATION: ("Setup", "Rig", "Match", "Transfer"),
    PlanKind.RIG: ("Setup", "Rig"),
}


@dataclass
class TransferPlan:
    """What the Setup step proposes once the models are known."""

    kind: PlanKind
    source_id: Optional[str] = None
    destination_id: Optional[str] = None
    title: str = ""
    message: str = ""
    issues: List[str] = field(default_factory=list)
    can_swap: bool = False

    @property
    def ready(self) -> bool:
        return self.kind in _STEPS

    @property
    def steps(self) -> List[str]:
        return list(_STEPS.get(self.kind, ("Setup",)))

    @property
    def first_step(self) -> Optional[str]:
        """Page to open when the plan starts: ``"rig"``, ``"match"`` or None."""
        if self.kind == PlanKind.ANIMATION:
            return "match"
        if self.kind in (PlanKind.RIG_THEN_ANIMATION, PlanKind.RIG):
            return "rig"
        return None

    @property
    def action_label(self) -> str:
        return {"match": "Start: Match ›", "rig": "Start: Rig ›"}.get(self.first_step, "")

    @property
    def transfers_animation(self) -> bool:
        return self.kind in (PlanKind.ANIMATION, PlanKind.RIG_THEN_ANIMATION)


def _describe(character: Character, label: str) -> str:
    text = "{} ({}) has {}".format(label, character.name, character.contents())
    if character.has_anim:
        text += ", {} frames".format(character.anim.frame_count)
        if character.anim.transferred:
            text += " transferred by RigFlow"
    return text + "."


def _pick_source(a: Character, b: Character, preferred: Optional[str]):
    """Return (source, destination, note) following the owner's rules."""
    for candidate, other in ((a, b), (b, a)):
        if preferred == candidate.character_id and candidate.has_anim:
            return candidate, other, None
    authored = [c for c in (a, b) if c.has_authored_anim]
    animated = [c for c in (a, b) if c.has_anim]
    if len(authored) == 1:
        return authored[0], b if authored[0] is a else a, None
    if len(animated) == 1:
        return animated[0], b if animated[0] is a else a, None
    if len(animated) == 2:
        return a, b, "Both models are animated; Model A is used as the source. Swap the direction if needed."
    return None, None, None


def derive_plan(characters: Sequence[Character], preferred_source_id: Optional[str] = None) -> TransferPlan:
    """Build the plan for the models in Setup order (only the first two take part)."""
    if not characters:
        return TransferPlan(PlanKind.EMPTY, title="Add a model",
                            message="Drop a Maya scene, an FBX or an OBJ, or use the Maya selection. "
                                    "RigFlow detects the mesh, the rig and the animation it contains.")
    labels = [model_label(i) for i in range(len(characters))]
    if len(characters) == 1:
        only = characters[0]
        if only.has_anim:
            hint = "Add the model that should receive it."
        elif only.has_rig:
            hint = "Add an animated model (for example Mixamo joints) to transfer from, or a mesh to rig."
        elif only.has_mesh:
            hint = "Add a rigged or animated model to transfer its rig and animation onto this mesh."
        else:
            hint = "This model has no usable content. Replace it with a mesh or a skeleton."
        return TransferPlan(PlanKind.NEED_SECOND, title="Add a second model",
                            message=_describe(only, labels[0]) + " " + hint)
    a, b = characters[0], characters[1]
    issues = ["Only Model A and Model B take part; remove the others or reorder."] if len(characters) > 2 else []
    description = _describe(a, labels[0]) + " " + _describe(b, labels[1])
    source, destination, note = _pick_source(a, b, preferred_source_id)
    if source is None:
        rigged = [c for c in (a, b) if c.has_rig]
        mesh_only = [c for c in (a, b) if c.has_mesh and not c.has_rig]
        if len(rigged) == 1 and len(mesh_only) == 1:
            src, dst = rigged[0], mesh_only[0]
            return TransferPlan(PlanKind.RIG, src.character_id, dst.character_id,
                                "Transfer rig · {} → {}".format(labels[characters.index(src)], labels[characters.index(dst)]),
                                description + " Neither model is animated: copy {}'s skeleton onto {}'s mesh and bind it.".format(
                                    labels[characters.index(src)], labels[characters.index(dst)]), issues)
        issues.append("Neither model is animated.")
        return TransferPlan(PlanKind.NOTHING, title="Nothing to transfer",
                            message=description + " Add an animated model to transfer from.", issues=issues)
    if note:
        issues.append(note)
    src_label, dst_label = labels[characters.index(source)], labels[characters.index(destination)]
    can_swap = a.has_anim and b.has_anim
    if not source.has_rig:
        issues.append("{} is animated but its skeleton could not be read.".format(src_label))
        return TransferPlan(PlanKind.NOTHING, source.character_id, destination.character_id,
                            "Nothing to transfer", description, issues, can_swap)
    if destination.has_rig:
        notes = []
        if not source.has_mesh:
            notes.append("{} is joints only (mocap).".format(src_label))
        if not destination.has_mesh:
            notes.append("{} is joints only; the animation lands on its skeleton.".format(dst_label))
        if destination.has_anim and not destination.anim.transferred:
            notes.append("{} already has animation; the transfer goes to a new animation layer.".format(dst_label))
        return TransferPlan(PlanKind.ANIMATION, source.character_id, destination.character_id,
                            "Transfer animation · {} → {}".format(src_label, dst_label),
                            " ".join([description, "Match the joints, preview and transfer."] + notes),
                            issues, can_swap)
    if destination.has_mesh:
        return TransferPlan(PlanKind.RIG_THEN_ANIMATION, source.character_id, destination.character_id,
                            "Transfer rig, then animation · {} → {}".format(src_label, dst_label),
                            description + " {} has no rig: copy {}'s skeleton onto its mesh, bind it, then transfer the animation.".format(
                                dst_label, src_label), issues, can_swap)
    issues.append("{} has neither a mesh nor a rig.".format(dst_label))
    return TransferPlan(PlanKind.NOTHING, source.character_id, destination.character_id,
                        "Nothing to transfer", description, issues, can_swap)
