"""Pure description of one *model* added in Setup and what it brings along.

A model is anything the artist adds with the single **Add** action: a Maya
scene, an FBX, an OBJ or a selection in the current scene. RigFlow inspects it
and fills up to three slots:

* ``mesh`` – polygon geometry (skinned or not),
* ``rig``  – a joint hierarchy, labelled against the humanoid template,
* ``anim`` – keys found on that joint hierarchy.

The slots are plain data. Nothing here touches Maya; ``rigflow.scene`` fills
them and :mod:`rigflow.core.plan` reasons about them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from rigflow.mapping.model import SkeletonLabeling
from rigflow.skeleton.model import Skeleton
from rigflow.skeleton.roles import REQUIRED_ROLES

MODEL_LETTERS = "ABCDEFGH"


def new_character_id() -> str:
    return uuid.uuid4().hex[:8]


def model_label(index: int) -> str:
    """Display label for the model at ``index`` in the Setup step: ``Model A``..."""
    return "Model {}".format(MODEL_LETTERS[index] if 0 <= index < len(MODEL_LETTERS) else index + 1)


@dataclass
class MeshSlot:
    """Polygon geometry detected on a model."""

    meshes: List[str] = field(default_factory=list)
    vertex_count: int = 0
    skinned: bool = False

    @property
    def valid(self) -> bool:
        return bool(self.meshes)

    def describe(self) -> str:
        return "{} mesh{} · {:,} vertices · {}".format(
            len(self.meshes), "" if len(self.meshes) == 1 else "es", self.vertex_count,
            "Skinned" if self.skinned else "Unskinned")


@dataclass
class RigSlot:
    """Joint hierarchy detected on a model, read at rest pose and labelled."""

    root: str
    skeleton: Optional[Skeleton] = None
    labeling: Optional[SkeletonLabeling] = None
    convention: str = "Unknown"
    warnings: List[str] = field(default_factory=list)

    @property
    def joint_count(self) -> int:
        return len(self.skeleton) if self.skeleton is not None else 0

    @property
    def valid(self) -> bool:
        return self.skeleton is not None and self.joint_count > 0

    @property
    def required_roles_found(self) -> int:
        if self.labeling is None:
            return 0
        return len(set(REQUIRED_ROLES) & set(self.labeling.roles()))

    @property
    def complete(self) -> bool:
        """True when every required humanoid role was identified."""
        return self.valid and self.required_roles_found == len(REQUIRED_ROLES)

    def describe(self) -> str:
        return "{} · {} joints\n{} · {}/{} required roles".format(
            self.root.rsplit("|", 1)[-1], self.joint_count, self.convention,
            self.required_roles_found, len(REQUIRED_ROLES))


@dataclass
class AnimSlot:
    """Keys found on the model's joints."""

    frame_range: Tuple[float, float] = (1.0, 1.0)
    fps: float = 24.0
    animated_joints: int = 0
    transferred: bool = False  #: Written by a RigFlow transfer rather than authored.

    @property
    def frame_count(self) -> int:
        return int(round(self.frame_range[1] - self.frame_range[0])) + 1

    @property
    def range_label(self) -> str:
        return "{:g}–{:g}".format(*self.frame_range)

    def describe(self) -> str:
        text = "{} · {} frames · {:g} fps · {} joints keyed".format(
            self.range_label, self.frame_count, self.fps, self.animated_joints)
        return text + ("\nTransferred by RigFlow" if self.transferred else "")


@dataclass
class Character:
    """One model in Setup: its origin plus the three detected slots."""

    name: str
    character_id: str = field(default_factory=new_character_id)
    source_path: Optional[str] = None
    namespace: Optional[str] = None
    mesh: Optional[MeshSlot] = None
    rig: Optional[RigSlot] = None
    anim: Optional[AnimSlot] = None
    notes: List[str] = field(default_factory=list)

    @property
    def has_mesh(self) -> bool:
        return self.mesh is not None and self.mesh.valid

    @property
    def has_rig(self) -> bool:
        return self.rig is not None and self.rig.valid

    @property
    def has_anim(self) -> bool:
        return self.anim is not None and self.anim.animated_joints > 0

    @property
    def has_authored_anim(self) -> bool:
        """Animation that did not come from a RigFlow transfer."""
        return self.has_anim and not self.anim.transferred

    @property
    def usable(self) -> bool:
        return self.has_mesh or self.has_rig

    def contents(self) -> str:
        """Human sentence fragment: ``mesh, rig and animation`` / ``mesh only``..."""
        parts = []
        if self.has_mesh:
            parts.append("mesh")
        if self.has_rig:
            parts.append("rig")
        if self.has_anim:
            parts.append("animation")
        if not parts:
            return "nothing usable"
        if len(parts) == 1:
            return parts[0] + " only"
        return ", ".join(parts[:-1]) + " and " + parts[-1]

    def summary(self) -> Dict[str, object]:
        return {
            "id": self.character_id,
            "name": self.name,
            "mesh": self.mesh.describe() if self.has_mesh else None,
            "rig": self.rig.describe() if self.has_rig else None,
            "anim": self.anim.describe() if self.has_anim else None,
            "contents": self.contents(),
        }
