"""Pure-Python description of one animation handled by RigFlow."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from rigflow.mapping.model import JointMapping
from rigflow.skeleton.model import Skeleton


class ClipStatus(str, Enum):
    IMPORTED = "imported"  #: Source loaded, no mapping yet.
    MAPPED = "mapped"  #: Mapping exists and validates without errors.
    NEEDS_REVIEW = "needs_review"  #: Mapping has red rows or validation errors.
    PREVIEWING = "previewing"  #: Live retarget connected (nothing baked).
    TRANSFERRED = "transferred"  #: Baked onto the destination.
    ERROR = "error"  #: Last operation failed; see ``notes``.

    @property
    def label(self) -> str:
        return {
            "imported": "Imported",
            "mapped": "Ready to transfer",
            "needs_review": "Needs review",
            "previewing": "Previewing",
            "transferred": "Transferred",
            "error": "Error",
        }[self.value]


def new_clip_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class AnimationClip:
    """One source animation and everything RigFlow knows about it."""

    name: str
    clip_id: str = field(default_factory=new_clip_id)
    source_path: Optional[str] = None
    namespace: Optional[str] = None
    source_root: Optional[str] = None
    source_skeleton: Optional[Skeleton] = None
    convention: str = "Unknown"
    frame_range: Tuple[float, float] = (1.0, 1.0)
    fps: float = 24.0
    status: ClipStatus = ClipStatus.IMPORTED
    mapping: Optional[JointMapping] = None
    result: Dict[str, object] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def frame_count(self) -> int:
        return int(round(self.frame_range[1] - self.frame_range[0])) + 1

    @property
    def duration_seconds(self) -> float:
        return (self.frame_count - 1) / self.fps if self.fps else 0.0

    @property
    def range_label(self) -> str:
        start, end = self.frame_range
        return "{:g}–{:g}".format(start, end)

    @property
    def joint_count(self) -> int:
        return len(self.source_skeleton) if self.source_skeleton is not None else 0

    def summary(self) -> Dict[str, object]:
        """Compact description for the Animation list in the main window."""
        return {
            "id": self.clip_id,
            "name": self.name,
            "convention": self.convention,
            "range": self.range_label,
            "frames": self.frame_count,
            "status": self.status.label,
            "mapped": self.mapping is not None,
        }
