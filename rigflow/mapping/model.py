"""Data model for skeleton labelings and source/destination joint mappings."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from rigflow.core.config import CONFIDENCE_MANUAL, GREEN_THRESHOLD, YELLOW_THRESHOLD
from rigflow.skeleton.roles import is_required, sort_roles


class MatchStatus(str, Enum):
    """Visual status of one role in the mapping table."""

    GREEN = "green"  #: High confidence or manually set; both joints present.
    YELLOW = "yellow"  #: Both joints present but the match needs review.
    RED = "red"  #: Required role missing, conflicting or unreliable.
    UNAVAILABLE = "unavailable"  #: Optional role absent on one side (shown gray).
    EXCLUDED = "excluded"  #: The user chose not to transfer this role.


def status_for(
    confidence: float,
    has_source: bool,
    has_destination: bool,
    required: bool,
    manual: bool = False,
    excluded: bool = False,
) -> MatchStatus:
    """Derive the display status of a match from its facts."""
    if excluded:
        return MatchStatus.EXCLUDED
    if has_source and has_destination:
        if manual or confidence >= GREEN_THRESHOLD:
            return MatchStatus.GREEN
        if confidence >= YELLOW_THRESHOLD:
            return MatchStatus.YELLOW
        return MatchStatus.RED
    return MatchStatus.RED if required else MatchStatus.UNAVAILABLE


@dataclass
class JointLabel:
    """Role assigned to one joint of one skeleton."""

    joint: str
    role: Optional[str] = None
    confidence: float = 0.0
    evidence: Tuple[str, ...] = ()
    notes: List[str] = field(default_factory=list)
    ignored: Optional[str] = None

    @property
    def assigned(self) -> bool:
        return self.role is not None


@dataclass
class SkeletonLabeling:
    """Roles assigned to every joint of a skeleton."""

    skeleton_name: str = ""
    labels: Dict[str, JointLabel] = field(default_factory=dict)
    convention: str = "Unknown"
    notes: List[str] = field(default_factory=list)

    def role_of(self, joint: str) -> Optional[str]:
        label = self.labels.get(joint)
        return label.role if label else None

    def confidence_of(self, joint: str) -> float:
        label = self.labels.get(joint)
        return label.confidence if label else 0.0

    def joint_for(self, role: str) -> Optional[str]:
        for label in self.labels.values():
            if label.role == role:
                return label.joint
        return None

    def roles(self) -> Dict[str, str]:
        """``role -> joint`` for every assigned role."""
        return {label.role: label.joint for label in self.labels.values() if label.role}

    def unassigned_joints(self) -> List[str]:
        return [l.joint for l in self.labels.values() if l.role is None and l.ignored is None]

    def ignored_joints(self) -> Dict[str, str]:
        """``joint -> reason`` for joints deliberately left out."""
        return {l.joint: l.ignored for l in self.labels.values() if l.ignored}


@dataclass
class JointMatch:
    """One row of the mapping table: a role with its source and destination joints."""

    role: str
    source: Optional[str] = None
    destination: Optional[str] = None
    confidence: float = 0.0
    status: MatchStatus = MatchStatus.UNAVAILABLE
    manual: bool = False
    excluded: bool = False
    notes: List[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.source is not None and self.destination is not None

    @property
    def transferable(self) -> bool:
        """True when this row will actually be used by the retargeter."""
        return self.complete and not self.excluded

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "source": self.source,
            "destination": self.destination,
            "confidence": round(self.confidence, 4),
            "status": self.status.value,
            "manual": self.manual,
            "excluded": self.excluded,
            "notes": list(self.notes),
        }


class JointMapping:
    """Source-to-destination joint correspondence keyed by canonical role.

    Automatic results are stored per role; manual overrides are kept in a
    separate dictionary so that recomputing the automatic mapping (for example
    after the user changes the destination skeleton) never discards the
    user's corrections unless :meth:`clear_manual` is called explicitly.
    """

    FORMAT_VERSION = 1

    def __init__(self, source_name: str = "", destination_name: str = ""):
        self.source_name = source_name
        self.destination_name = destination_name
        self.matches: Dict[str, JointMatch] = {}
        self.manual: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
        self.excluded: Set[str] = set()

    # --- editing ---------------------------------------------------------------------

    def set_auto(
        self,
        role: str,
        source: Optional[str],
        destination: Optional[str],
        confidence: float,
        notes: Optional[List[str]] = None,
    ) -> JointMatch:
        """Record an automatic match. Manual overrides are re-applied afterwards."""
        match = JointMatch(
            role=role,
            source=source,
            destination=destination,
            confidence=confidence,
            notes=list(notes or []),
            excluded=role in self.excluded,
        )
        match.status = status_for(
            confidence, source is not None, destination is not None, is_required(role),
            excluded=match.excluded,
        )
        self.matches[role] = match
        if role in self.manual:
            self._apply_one_manual(role)
        return match

    def set_manual(self, role: str, source: Optional[str], destination: Optional[str]) -> JointMatch:
        """Store a user correction for ``role`` and apply it."""
        self.manual[role] = (source, destination)
        if role not in self.matches:
            self.matches[role] = JointMatch(role=role)
        return self._apply_one_manual(role)

    def clear_manual(self, role: str) -> None:
        """Drop the manual override of one role (the automatic match remains)."""
        self.manual.pop(role, None)
        match = self.matches.get(role)
        if match is not None:
            match.manual = False
            match.confidence = 0.0 if not match.complete else match.confidence
            match.status = status_for(
                match.confidence, match.source is not None, match.destination is not None,
                is_required(role), excluded=match.excluded,
            )

    def clear_all_manual(self) -> None:
        for role in list(self.manual):
            self.clear_manual(role)

    def set_excluded(self, role: str, excluded: bool = True) -> None:
        """Mark a role as not-to-transfer (or re-enable it)."""
        if excluded:
            self.excluded.add(role)
        else:
            self.excluded.discard(role)
        match = self.matches.get(role)
        if match is not None:
            match.excluded = excluded
            match.status = status_for(
                match.confidence, match.source is not None, match.destination is not None,
                is_required(role), manual=match.manual, excluded=excluded,
            )

    def apply_manual(self) -> None:
        for role in list(self.manual):
            self._apply_one_manual(role)

    def _apply_one_manual(self, role: str) -> JointMatch:
        source, destination = self.manual[role]
        match = self.matches.setdefault(role, JointMatch(role=role))
        match.source = source
        match.destination = destination
        match.manual = True
        match.confidence = CONFIDENCE_MANUAL if (source and destination) else 0.0
        match.excluded = role in self.excluded
        match.status = status_for(
            match.confidence, source is not None, destination is not None, is_required(role),
            manual=True, excluded=match.excluded,
        )
        return match

    # --- queries -------------------------------------------------------------------------

    def sorted_matches(self) -> List[JointMatch]:
        return [self.matches[r] for r in sort_roles(self.matches)]

    def complete_pairs(self) -> List[Tuple[str, str, str]]:
        """``(role, source, destination)`` for every transferable match."""
        return [
            (m.role, m.source, m.destination)  # type: ignore[misc]
            for m in self.sorted_matches()
            if m.transferable
        ]

    def by_status(self) -> Dict[MatchStatus, List[JointMatch]]:
        groups: Dict[MatchStatus, List[JointMatch]] = {s: [] for s in MatchStatus}
        for match in self.sorted_matches():
            groups[match.status].append(match)
        return groups

    def source_joints_used(self) -> Set[str]:
        return {m.source for m in self.matches.values() if m.source and not m.excluded}

    def destination_joints_used(self) -> Set[str]:
        return {m.destination for m in self.matches.values() if m.destination and not m.excluded}

    def summary(self) -> Dict[str, int]:
        groups = self.by_status()
        return {status.value: len(items) for status, items in groups.items()}

    @property
    def has_blocking_issues(self) -> bool:
        return any(m.status is MatchStatus.RED for m in self.matches.values())

    # --- serialisation ---------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "format": "rigflow-mapping",
            "version": self.FORMAT_VERSION,
            "source_name": self.source_name,
            "destination_name": self.destination_name,
            "matches": [m.to_dict() for m in self.sorted_matches()],
            "manual": {role: list(pair) for role, pair in self.manual.items()},
            "excluded": sorted(self.excluded),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JointMapping":
        if data.get("format") not in (None, "rigflow-mapping"):
            raise ValueError("Not a RigFlow mapping file")
        mapping = cls(data.get("source_name", ""), data.get("destination_name", ""))
        mapping.excluded = set(data.get("excluded", []))
        for item in data.get("matches", []):
            mapping.set_auto(
                item["role"], item.get("source"), item.get("destination"),
                float(item.get("confidence", 0.0)), item.get("notes", []),
            )
        for role, pair in data.get("manual", {}).items():
            mapping.set_manual(role, pair[0], pair[1])
        return mapping

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "JointMapping({} roles, {})".format(len(self.matches), self.summary())
