"""Canonical humanoid roles.

RigFlow labels every skeleton against one shared vocabulary so that a source
and a destination skeleton can be paired by *role* instead of by name. The
vocabulary is HumanIK's slot naming (``Hips``, ``Spine``, ``Spine1``…,
``LeftArm``, ``LeftForeArm``, ``LeftHand``, ``LeftHandIndex1``…) because:

* Mixamo skeletons use these exact names.
* The HumanIK retargeting backend needs them for characterisation.
* They are a widely understood industry vocabulary.

Roles are plain strings; this module provides the grammar to build, parse and
mirror them plus the template hierarchy used for validation.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Side(str, Enum):
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"

    @property
    def prefix(self) -> str:
        return {"left": "Left", "right": "Right"}.get(self.value, "")

    def mirrored(self) -> "Side":
        if self is Side.LEFT:
            return Side.RIGHT
        if self is Side.RIGHT:
            return Side.LEFT
        return self


#: Body parts located on the center line.
CENTER_PARTS = ("Hips", "Spine", "Neck", "Head")
#: Body parts that exist once per side.
SIDE_PARTS = ("Shoulder", "Arm", "ForeArm", "Hand", "UpLeg", "Leg", "Foot", "ToeBase")
#: Finger parts (indexed 1..4 from the base phalanx to the tip).
FINGER_PARTS = ("HandThumb", "HandIndex", "HandMiddle", "HandRing", "HandPinky")
#: Parts that form a numbered chain on the center line (``Spine``, ``Spine1``...).
CHAIN_PARTS = ("Spine", "Neck")

ALL_PARTS = CENTER_PARTS + SIDE_PARTS + FINGER_PARTS

#: Template parent part for each part. ``Neck`` and ``Shoulder`` hang from the
#: *last* spine joint; ``Spine`` chains and fingers index upward.
TEMPLATE_PARENT_PART: Dict[str, Optional[str]] = {
    "Hips": None,
    "Spine": "Hips",
    "Neck": "Spine",
    "Head": "Neck",
    "Shoulder": "Spine",
    "Arm": "Shoulder",
    "ForeArm": "Arm",
    "Hand": "ForeArm",
    "UpLeg": "Hips",
    "Leg": "UpLeg",
    "Foot": "Leg",
    "ToeBase": "Foot",
    "HandThumb": "Hand",
    "HandIndex": "Hand",
    "HandMiddle": "Hand",
    "HandRing": "Hand",
    "HandPinky": "Hand",
}

#: Parts that may legitimately be absent (the template parent chain skips them).
OPTIONAL_PARTS = ("Neck", "Shoulder", "ToeBase") + FINGER_PARTS

#: Minimum set HumanIK needs to characterise a biped. Missing any of these
#: makes a mapping invalid.
REQUIRED_ROLES = (
    "Hips",
    "Spine",
    "Head",
    "LeftArm",
    "LeftForeArm",
    "LeftHand",
    "RightArm",
    "RightForeArm",
    "RightHand",
    "LeftUpLeg",
    "LeftLeg",
    "LeftFoot",
    "RightUpLeg",
    "RightLeg",
    "RightFoot",
)

#: Strongly recommended for good results, but not mandatory.
RECOMMENDED_ROLES = ("Neck", "LeftShoulder", "RightShoulder", "LeftToeBase", "RightToeBase")

_ROLE_RE = re.compile(
    r"^(?P<side>Left|Right)?"
    r"(?P<part>Hips|Spine|Neck|Head|Shoulder|Arm|ForeArm|"
    r"Hand(?:Thumb|Index|Middle|Ring|Pinky)?|UpLeg|Leg|Foot|ToeBase)"
    r"(?P<index>\d*)$"
)


def role_name(part: str, side: Side = Side.CENTER, index: int = 0) -> str:
    """Build a role string from its components.

    >>> role_name("Spine")            -> "Spine"
    >>> role_name("Spine", index=2)   -> "Spine2"
    >>> role_name("Arm", Side.LEFT)   -> "LeftArm"
    >>> role_name("HandIndex", Side.RIGHT, 1) -> "RightHandIndex1"
    """
    if part not in ALL_PARTS:
        raise ValueError("Unknown body part: {}".format(part))
    if part in CENTER_PARTS:
        if part in CHAIN_PARTS and index > 0:
            return "{}{}".format(part, index)
        return part
    if side is Side.CENTER:
        raise ValueError("Part {} requires a side".format(part))
    if part in FINGER_PARTS:
        return "{}{}{}".format(side.prefix, part, max(1, index))
    return "{}{}".format(side.prefix, part)


def parse_role(role: str) -> Optional[Tuple[Side, str, int]]:
    """Split a role into ``(side, part, index)``; ``None`` if not a valid role."""
    match = _ROLE_RE.match(role)
    if not match:
        return None
    side_text = match.group("side")
    side = Side.LEFT if side_text == "Left" else Side.RIGHT if side_text == "Right" else Side.CENTER
    part = match.group("part")
    index = int(match.group("index")) if match.group("index") else 0
    if part in CENTER_PARTS and side is not Side.CENTER:
        return None
    if part not in CENTER_PARTS and side is Side.CENTER:
        return None
    if part in FINGER_PARTS and not 1 <= index <= 4:
        return None
    if part in CHAIN_PARTS and index >= 10:
        return None
    if part not in CHAIN_PARTS and part not in FINGER_PARTS and index != 0:
        return None
    return side, part, index


def is_valid_role(role: str) -> bool:
    return parse_role(role) is not None


def role_part(role: str) -> Optional[str]:
    parsed = parse_role(role)
    return parsed[1] if parsed else None


def role_side(role: str) -> Side:
    parsed = parse_role(role)
    return parsed[0] if parsed else Side.CENTER


def mirror_role(role: str) -> str:
    """``LeftArm`` <-> ``RightArm``; center roles are returned unchanged."""
    parsed = parse_role(role)
    if parsed is None:
        return role
    side, part, index = parsed
    return role_name(part, side.mirrored(), index)


def is_required(role: str) -> bool:
    return role in REQUIRED_ROLES


def template_ancestor_parts(part: str) -> List[str]:
    """Parts expected above ``part`` in the template, nearest first."""
    result: List[str] = []
    current = TEMPLATE_PARENT_PART.get(part)
    while current is not None:
        result.append(current)
        current = TEMPLATE_PARENT_PART.get(current)
    return result


def display_name(role: str) -> str:
    """Human-friendly label: ``LeftForeArm`` -> ``Left Fore Arm``."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)", " ", role)


def canonical_roles() -> List[str]:
    """Every role RigFlow can assign, in a stable display order."""
    roles: List[str] = ["Hips"]
    roles += [role_name("Spine", index=i) for i in range(10)]
    roles += [role_name("Neck", index=i) for i in range(10)]
    roles.append("Head")
    for side in (Side.LEFT, Side.RIGHT):
        for part in ("Shoulder", "Arm", "ForeArm", "Hand"):
            roles.append(role_name(part, side))
        for finger in FINGER_PARTS:
            roles += [role_name(finger, side, i) for i in range(1, 5)]
    for side in (Side.LEFT, Side.RIGHT):
        for part in ("UpLeg", "Leg", "Foot", "ToeBase"):
            roles.append(role_name(part, side))
    return roles


#: Display order index for sorting mappings in the UI.
ROLE_ORDER: Dict[str, int] = {role: i for i, role in enumerate(canonical_roles())}


def sort_roles(roles) -> List[str]:
    return sorted(roles, key=lambda r: ROLE_ORDER.get(r, len(ROLE_ORDER)))
