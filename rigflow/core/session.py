"""Session state shared by the UI and the services.

The :class:`Session` is a plain observable container: it knows the models
added in Setup (and the plan derived from them), the active destination
model/rig and the list of animation clips, and notifies listeners when any of
them changes. It never touches Maya; the services in
``rigflow.scene`` / ``rigflow.retargeting`` fill it, and the widgets in
``rigflow.ui`` render it. Keeping this object pure makes the UI testable with
fake data and keeps the engine usable from scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from rigflow.animation.clip import AnimationClip
from rigflow.core.character import Character, model_label
from rigflow.core.plan import TransferPlan, derive_plan
from rigflow.core.similarity import MeshSimilarity
from rigflow.mapping.model import SkeletonLabeling
from rigflow.skeleton.model import Skeleton


class SessionEvent(str, Enum):
    MODEL_CHANGED = "model_changed"
    RIG_CHANGED = "rig_changed"
    CLIPS_CHANGED = "clips_changed"
    ACTIVE_CLIP_CHANGED = "active_clip_changed"
    CHARACTERS_CHANGED = "characters_changed"  #: Models added/removed/replaced in Setup.
    PLAN_CHANGED = "plan_changed"  #: The proposed process changed (payload: TransferPlan).
    STATUS = "status"  #: Transient status/progress message for the status bar.


@dataclass
class ModelInfo:
    """Destination geometry selected in the Model section."""

    name: str
    meshes: List[str] = field(default_factory=list)
    vertex_count: int = 0
    skinned: bool = False
    skeleton_root: Optional[str] = None
    message: str = ""

    @property
    def valid(self) -> bool:
        return bool(self.meshes)


@dataclass
class RigInfo:
    """Destination skeleton selected in the Rig section."""

    name: str
    root: str
    skeleton: Optional[Skeleton] = None
    labeling: Optional[SkeletonLabeling] = None
    convention: str = "Unknown"
    message: str = ""
    warnings: List[str] = field(default_factory=list)

    @property
    def joint_count(self) -> int:
        return len(self.skeleton) if self.skeleton is not None else 0

    @property
    def valid(self) -> bool:
        return self.skeleton is not None and self.joint_count > 0


Listener = Callable[[SessionEvent, object], None]


class Session:
    """Observable application state."""

    def __init__(self):
        self.model: Optional[ModelInfo] = None
        self.rig: Optional[RigInfo] = None
        self.clips: List[AnimationClip] = []
        self.active_clip_id: Optional[str] = None
        self.characters: List[Character] = []
        self.preferred_source_id: Optional[str] = None
        self.mesh_similarity: Optional[MeshSimilarity] = None
        self.started_steps: Optional[List[str]] = None
        self.plan: TransferPlan = derive_plan([])
        self._listeners: List[Listener] = []

    # --- observers -----------------------------------------------------------------------

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Register a listener; returns a function that unsubscribes it."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _emit(self, event: SessionEvent, payload: object = None) -> None:
        for listener in list(self._listeners):
            listener(event, payload)

    def status(self, message: str, level: str = "info") -> None:
        """Broadcast a transient status message (``level``: info/warning/error/success)."""
        self._emit(SessionEvent.STATUS, {"message": message, "level": level})

    # --- models (Setup step) ---------------------------------------------------------------

    def add_character(self, character: Character) -> Character:
        self.started_steps = None
        self.characters.append(character)
        self._characters_changed()
        return character

    def remove_character(self, character_id: str) -> Optional[Character]:
        character = self.get_character(character_id)
        if character is None:
            return None
        self.characters.remove(character)
        self.started_steps = None
        if self.preferred_source_id == character_id:
            self.preferred_source_id = None
        self._characters_changed()
        return character

    def replace_character(self, character_id: str, character: Character) -> Character:
        """Swap a model in place (same position, same id)."""
        self.started_steps = None
        for index, existing in enumerate(self.characters):
            if existing.character_id == character_id:
                character.character_id = character_id
                self.characters[index] = character
                break
        else:
            self.characters.append(character)
        self._characters_changed()
        return character

    def character_updated(self, character_id: str) -> None:
        """Notify listeners that a model's slots changed in place."""
        self._characters_changed()

    def get_character(self, character_id: Optional[str]) -> Optional[Character]:
        for character in self.characters:
            if character.character_id == character_id:
                return character
        return None

    def label_for(self, character_id: Optional[str]) -> str:
        """``Model A`` / ``Model B`` ... by Setup position."""
        for index, character in enumerate(self.characters):
            if character.character_id == character_id:
                return model_label(index)
        return "Model"

    def set_preferred_source(self, character_id: Optional[str]) -> TransferPlan:
        self.preferred_source_id = character_id
        return self.recompute_plan()

    def swap_direction(self) -> TransferPlan:
        """Make the current destination the preferred source."""
        return self.set_preferred_source(self.plan.destination_id)

    def recompute_plan(self) -> TransferPlan:
        self.plan = derive_plan(self.characters, self.preferred_source_id, self.mesh_similarity)
        self._emit(SessionEvent.PLAN_CHANGED, self.plan)
        return self.plan

    def _characters_changed(self) -> None:
        self.mesh_similarity = None
        self._emit(SessionEvent.CHARACTERS_CHANGED, self.characters)
        self.recompute_plan()

    @property
    def source(self) -> Optional[Character]:
        return self.get_character(self.plan.source_id)

    @property
    def destination(self) -> Optional[Character]:
        return self.get_character(self.plan.destination_id)

    # --- model / rig ---------------------------------------------------------------------

    def set_model(self, model: Optional[ModelInfo]) -> None:
        self.model = model
        self._emit(SessionEvent.MODEL_CHANGED, model)

    def set_rig(self, rig: Optional[RigInfo]) -> None:
        self.rig = rig
        self._emit(SessionEvent.RIG_CHANGED, rig)

    # --- clips ------------------------------------------------------------------------------

    def add_clip(self, clip: AnimationClip, activate: bool = True) -> AnimationClip:
        self.clips.append(clip)
        self._emit(SessionEvent.CLIPS_CHANGED, self.clips)
        if activate:
            self.set_active_clip(clip.clip_id)
        return clip

    def remove_clip(self, clip_id: str) -> Optional[AnimationClip]:
        clip = self.get_clip(clip_id)
        if clip is None:
            return None
        self.clips.remove(clip)
        if self.active_clip_id == clip_id:
            self.active_clip_id = self.clips[-1].clip_id if self.clips else None
            self._emit(SessionEvent.ACTIVE_CLIP_CHANGED, self.active_clip)
        self._emit(SessionEvent.CLIPS_CHANGED, self.clips)
        return clip

    def replace_clip(self, clip_id: str, clip: AnimationClip) -> None:
        for index, existing in enumerate(self.clips):
            if existing.clip_id == clip_id:
                clip.clip_id = clip_id
                self.clips[index] = clip
                break
        else:
            self.clips.append(clip)
        self._emit(SessionEvent.CLIPS_CHANGED, self.clips)
        if self.active_clip_id == clip_id:
            self._emit(SessionEvent.ACTIVE_CLIP_CHANGED, clip)

    def clip_updated(self, clip_id: str) -> None:
        """Notify listeners that a clip's fields changed in place."""
        self._emit(SessionEvent.CLIPS_CHANGED, self.clips)
        if self.active_clip_id == clip_id:
            self._emit(SessionEvent.ACTIVE_CLIP_CHANGED, self.active_clip)

    def get_clip(self, clip_id: Optional[str]) -> Optional[AnimationClip]:
        for clip in self.clips:
            if clip.clip_id == clip_id:
                return clip
        return None

    def set_active_clip(self, clip_id: Optional[str]) -> None:
        if clip_id is not None and self.get_clip(clip_id) is None:
            raise KeyError("Unknown clip id: {}".format(clip_id))
        self.active_clip_id = clip_id
        self._emit(SessionEvent.ACTIVE_CLIP_CHANGED, self.active_clip)

    @property
    def active_clip(self) -> Optional[AnimationClip]:
        return self.get_clip(self.active_clip_id)

    # --- readiness ---------------------------------------------------------------------------

    @property
    def destination_ready(self) -> bool:
        """True when a valid destination rig is selected (the model is optional)."""
        return self.rig is not None and self.rig.valid

    def readiness(self) -> Dict[str, bool]:
        return {
            "model": self.model is not None and self.model.valid,
            "rig": self.destination_ready,
            "animation": bool(self.clips),
        }
