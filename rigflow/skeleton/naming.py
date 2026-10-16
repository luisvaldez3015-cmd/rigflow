"""Role inference from joint names.

Joint names are tokenised (``"LeftHandIndex1"`` -> ``left hand index 1``,
``"upperarm_twist_01_l"`` -> ``upperarm twist 01 l``) and matched against a
dictionary of body-part keywords that covers the naming conventions RigFlow
meets most often: Mixamo / HumanIK, Unreal Engine / MetaHuman, AdvancedSkeleton,
3ds Max Biped, Unity Humanoid, Daz Genesis and generic ``l_wrist_JNT`` styles.

The analyser is deliberately conservative:

* Joints that are clearly *not* body bones (end tips, twist/roll helpers,
  facial joints, controls, props) are marked **ignored** with a reason, so they
  are never mapped and never touched. This is what keeps facial rigs safe.
* Names that could mean two things (``shoulder`` = clavicle or upper arm,
  ``leg`` = thigh or shin) are reported as **ambiguous**; topology analysis
  resolves them in :mod:`rigflow.mapping.matcher`.
* Spine and neck chains are renumbered by hierarchy depth, so ``spine_01..05``
  (Unreal), ``Spine/Spine1/Spine2`` (Mixamo) and ``Spine1_M/Spine2_M/Chest_M``
  (AdvancedSkeleton) all become ``Spine, Spine1, ...``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from rigflow.core.config import MAX_CHAIN_JOINTS
from rigflow.skeleton.model import Skeleton
from rigflow.skeleton.roles import CENTER_PARTS, CHAIN_PARTS, FINGER_PARTS, Side, role_name
from rigflow.utils.strings import namespace_of, short_name, split_tokens

# --- Vocabulary ---------------------------------------------------------------------

LEFT_TOKENS = frozenset({"left", "l", "lf", "lft", "lt"})
RIGHT_TOKENS = frozenset({"right", "r", "rt", "rgt"})
CENTER_TOKENS = frozenset({"m", "c", "mid", "center", "centre"})

#: ``reason -> tokens``. A joint containing any of these tokens is ignored.
IGNORE_TOKENS: Tuple[Tuple[str, frozenset], ...] = (
    ("end", frozenset({"end", "tip", "nub", "eff", "effector", "endsite", "site"})),
    ("twist", frozenset({"twist", "roll", "twst"})),
    (
        "facial",
        frozenset(
            {
                "eye", "eyes", "jaw", "tongue", "brow", "eyebrow", "lip", "lips", "cheek", "ear",
                "nose", "teeth", "tooth", "facial", "face", "mouth", "eyelid", "chin", "forehead",
                "nostril", "pupil", "iris", "eyeball",
            }
        ),
    ),
    (
        "control",
        frozenset(
            {
                "ctrl", "ctl", "cntrl", "control", "controller", "con", "grp", "group", "offset",
                "loc", "locator", "ik", "fk", "pole", "pv", "switch", "handle", "driver", "driven",
                "drv", "null", "nul", "aux", "guide", "placement", "orient",
            }
        ),
    ),
    (
        "accessory",
        frozenset(
            {
                "weapon", "prop", "sword", "gun", "bag", "cloth", "hair", "skirt", "tail", "cape",
                "wing", "wings", "breast", "belly", "butt", "glute", "scarf", "strap", "pouch",
                "holster", "ponytail", "braid", "feather", "antenna", "horn", "backpack",
            }
        ),
    ),
    ("metacarpal", frozenset({"metacarpal", "inhand", "carpal"})),
    ("reference", frozenset({"reference", "ref", "trajectory"})),
    ("helper", frozenset({"helper", "corrective", "correct", "pec", "latissimus", "deltoid"})),
)

#: Two-token phrases, checked before single tokens.
PHRASES: Dict[Tuple[str, str], str] = {
    ("up", "leg"): "UpLeg",
    ("upper", "leg"): "UpLeg",
    ("lower", "leg"): "Leg",
    ("low", "leg"): "Leg",
    ("fore", "arm"): "ForeArm",
    ("lower", "arm"): "ForeArm",
    ("low", "arm"): "ForeArm",
    ("upper", "arm"): "Arm",
    ("up", "arm"): "Arm",
    ("toe", "base"): "ToeBase",
    ("toes", "base"): "ToeBase",
    ("hand", "thumb"): "HandThumb",
    ("hand", "index"): "HandIndex",
    ("hand", "middle"): "HandMiddle",
    ("hand", "ring"): "HandRing",
    ("hand", "pinky"): "HandPinky",
}

#: Single-token keywords. Value: ``(part, alternatives)``; alternatives mark ambiguity.
KEYWORDS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "hips": ("Hips", ()),
    "pelvis": ("Hips", ()),
    "cog": ("Hips", ()),
    "waist": ("Hips", ()),
    "spine": ("Spine", ()),
    "chest": ("Spine", ()),
    "torso": ("Spine", ()),
    "abdomen": ("Spine", ()),
    "ribcage": ("Spine", ()),
    "neck": ("Neck", ()),
    "head": ("Head", ()),
    "skull": ("Head", ()),
    "shoulder": ("Shoulder", ("Arm",)),
    "clavicle": ("Shoulder", ()),
    "clav": ("Shoulder", ()),
    "collar": ("Shoulder", ()),
    "scapula": ("Shoulder", ()),
    "arm": ("Arm", ()),
    "upperarm": ("Arm", ()),
    "humerus": ("Arm", ()),
    "shldr": ("Arm", ()),
    "bicep": ("Arm", ()),
    "forearm": ("ForeArm", ()),
    "lowerarm": ("ForeArm", ()),
    "elbow": ("ForeArm", ()),
    "radius": ("ForeArm", ()),
    "ulna": ("ForeArm", ()),
    "hand": ("Hand", ()),
    "wrist": ("Hand", ()),
    "thigh": ("UpLeg", ()),
    "femur": ("UpLeg", ()),
    "upleg": ("UpLeg", ()),
    "upperleg": ("UpLeg", ()),
    "leg": ("Leg", ("UpLeg",)),
    "knee": ("Leg", ()),
    "calf": ("Leg", ()),
    "shin": ("Leg", ()),
    "tibia": ("Leg", ()),
    "lowerleg": ("Leg", ()),
    "lowleg": ("Leg", ()),
    "foot": ("Foot", ()),
    "feet": ("Foot", ()),
    "ankle": ("Foot", ()),
    "toe": ("ToeBase", ()),
    "toes": ("ToeBase", ()),
    "ball": ("ToeBase", ()),
    "toebase": ("ToeBase", ()),
    "thumb": ("HandThumb", ()),
    "index": ("HandIndex", ()),
    "middle": ("HandMiddle", ()),
    "ring": ("HandRing", ()),
    "pinky": ("HandPinky", ()),
    "pinkie": ("HandPinky", ()),
    "little": ("HandPinky", ()),
}

#: Tokens that turn a finger-like token into a toe digit (not supported in v1).
TOE_QUALIFIERS = frozenset({"toe", "toes", "foot", "big", "small"})
#: Tokens that turn a toe token into an individual toe digit instead of the toe base.
TOE_DIGIT_QUALIFIERS = frozenset({"big", "small", "little", "index", "middle", "ring", "pinky", "thumb"})

CONF_EXPLICIT = 0.9
CONF_AMBIGUOUS = 0.6
CONF_ROOT_AS_HIPS = 0.4
CONF_FINGER_NO_DIGIT = 0.6
CONF_HIP_AS_UPLEG = 0.85


@dataclass
class NameAnalysis:
    """Result of analysing one joint name."""

    joint: str
    tokens: List[str] = field(default_factory=list)
    side: Side = Side.CENTER
    side_explicit: bool = False
    part: Optional[str] = None
    index: Optional[int] = None
    chain_index: Optional[int] = None
    alternatives: Tuple[str, ...] = ()
    ignored: Optional[str] = None
    confidence: float = 0.0

    @property
    def ambiguous(self) -> bool:
        return bool(self.alternatives)

    @property
    def role(self) -> Optional[str]:
        """Role implied by the name, or ``None`` when it cannot be determined."""
        if self.ignored or self.part is None:
            return None
        if self.part in CENTER_PARTS:
            if self.part in CHAIN_PARTS:
                idx = self.chain_index if self.chain_index is not None else (self.index or 0)
                return role_name(self.part, index=min(idx, MAX_CHAIN_JOINTS - 1))
            return role_name(self.part)
        if self.side is Side.CENTER:
            return None
        if self.part in FINGER_PARTS:
            idx = self.index if self.index else 1
            if idx > 4:
                return None
            return role_name(self.part, self.side, idx)
        return role_name(self.part, self.side)

    def candidate_roles(self) -> List[str]:
        """Primary role followed by the roles implied by the alternatives."""
        roles: List[str] = []
        primary = self.role
        if primary:
            roles.append(primary)
        if self.ignored or self.side is Side.CENTER:
            return roles
        for part in self.alternatives:
            if part in CENTER_PARTS:
                continue
            roles.append(role_name(part, self.side))
        return roles


# --- Analysis -------------------------------------------------------------------------


def analyze_name(name: str) -> NameAnalysis:
    """Analyse a single joint name."""
    tokens = split_tokens(name)
    result = NameAnalysis(joint=name, tokens=tokens)
    if not tokens:
        return result

    _detect_side(result)
    _detect_ignored(result)
    if result.ignored:
        return result
    _detect_part(result)
    _apply_special_cases(result)
    return result


def _detect_side(result: NameAnalysis) -> None:
    for token in result.tokens:
        if token in LEFT_TOKENS:
            result.side, result.side_explicit = Side.LEFT, True
            return
        if token in RIGHT_TOKENS:
            result.side, result.side_explicit = Side.RIGHT, True
            return
    for token in result.tokens:
        if token in CENTER_TOKENS:
            result.side, result.side_explicit = Side.CENTER, True
            return


def _detect_ignored(result: NameAnalysis) -> None:
    token_set = set(result.tokens)
    for reason, words in IGNORE_TOKENS:
        if token_set & words:
            result.ignored = reason
            return


def _detect_part(result: NameAnalysis) -> None:
    tokens = result.tokens
    part_pos: Optional[int] = None

    for i in range(len(tokens) - 1):
        phrase = (tokens[i], tokens[i + 1])
        if phrase in PHRASES:
            result.part = PHRASES[phrase]
            part_pos = i + 1
            break

    if result.part is None:
        for i, token in enumerate(tokens):
            if token in KEYWORDS:
                part, alternatives = KEYWORDS[token]
                result.part = part
                result.alternatives = alternatives
                part_pos = i
                break
            if token == "hip":
                result.part = "UpLeg" if result.side is not Side.CENTER else "Hips"
                part_pos = i
                break
            if token == "root":
                result.part = "Hips"
                result.alternatives = ()
                result.confidence = CONF_ROOT_AS_HIPS
                part_pos = i
                break

    if result.part is None:
        return

    # A finger token overrides "hand" when both are present (e.g. "l_hand_index_01").
    for i, token in enumerate(tokens):
        if token in KEYWORDS and KEYWORDS[token][0] in FINGER_PARTS and result.part == "Hand":
            result.part = KEYWORDS[token][0]
            result.alternatives = ()
            part_pos = i
            break

    # Numeric index: first digit token after the part token.
    if part_pos is not None:
        for token in tokens[part_pos + 1 :]:
            if token.isdigit():
                result.index = int(token)
                break
            if token in KEYWORDS and KEYWORDS[token][0] not in FINGER_PARTS and token != "finger":
                break

    if result.confidence == 0.0:
        result.confidence = CONF_AMBIGUOUS if result.alternatives else CONF_EXPLICIT


def _apply_special_cases(result: NameAnalysis) -> None:
    tokens = set(result.tokens)
    part = result.part
    if part is None:
        return

    if part in FINGER_PARTS:
        if tokens & TOE_QUALIFIERS:
            result.ignored = "toe_digit"
            return
        if result.index == 0:
            result.ignored = "metacarpal"
            return
        if result.index is None:
            result.confidence = CONF_FINGER_NO_DIGIT
        elif result.index > 4:
            result.ignored = "extra_finger_joint"
            return

    if part == "ToeBase" and tokens & TOE_DIGIT_QUALIFIERS:
        result.ignored = "toe_digit"
        return

    if part in CENTER_PARTS and result.side is not Side.CENTER and result.side_explicit:
        # e.g. "spine_04_latissimus_l": a sided spine joint is a muscle helper.
        result.ignored = "helper"
        return

    if part == "UpLeg" and "hip" in tokens:
        result.confidence = CONF_HIP_AS_UPLEG

    if part not in CENTER_PARTS and result.side is Side.CENTER:
        # Sided part without side information: the name alone cannot place it.
        result.confidence = min(result.confidence, 0.5)


def analyze_names(skeleton: Skeleton) -> Dict[str, NameAnalysis]:
    """Analyse every joint of a skeleton and renumber spine/neck chains by depth."""
    analyses = {name: analyze_name(name) for name in skeleton.joint_names}
    renumber_chains(skeleton, analyses)
    return analyses


def renumber_chains(skeleton: Skeleton, analyses: Dict[str, NameAnalysis]) -> None:
    """Assign ``chain_index`` to spine and neck joints by hierarchy depth.

    Joints beyond :data:`MAX_CHAIN_JOINTS` are marked ignored (``extra_chain``).
    """
    for part in CHAIN_PARTS:
        members = [
            a for a in analyses.values()
            if a.part == part and not a.ignored and a.side is Side.CENTER
        ]
        members.sort(key=lambda a: (skeleton.depth(a.joint), a.index or 0, a.joint))
        for i, analysis in enumerate(members):
            if i >= MAX_CHAIN_JOINTS:
                analysis.ignored = "extra_chain"
            else:
                analysis.chain_index = i


# --- Convention detection ---------------------------------------------------------------


def detect_convention(names: Iterable[str]) -> str:
    """Best-effort label of the naming convention, for display only."""
    names = list(names)
    shorts = {short_name(n) for n in names}
    lowers = {s.lower() for s in shorts}
    namespaces = {namespace_of(n).lower() for n in names}

    if any(ns.startswith("mixamorig") for ns in namespaces) or any(
        s.lower().startswith("mixamorig") for s in shorts
    ):
        return "Mixamo"
    if any(s.startswith("Bip0") for s in shorts) or any(
        n.rsplit("|", 1)[-1].startswith("Bip0") for n in names
    ):
        return "3ds Max Biped"
    if "pelvis" in lowers and ("spine_01" in lowers or "clavicle_l" in lowers or "thigh_l" in lowers):
        return "Unreal Engine / MetaHuman"
    if "Root_M" in shorts or ("Hip_L" in shorts and "Spine1_M" in shorts):
        return "AdvancedSkeleton"
    if any("_C0_" in s or "_L0_" in s or "_R0_" in s for s in shorts):
        return "mGear"
    if "LeftUpperArm" in shorts or "LeftLowerArm" in shorts:
        return "Unity Humanoid"
    if "lShldrBend" in shorts or "abdomenLower" in shorts or "lThighBend" in shorts:
        return "Daz Genesis"
    if {"Hips", "Spine", "LeftUpLeg", "LeftArm", "LeftForeArm"} <= shorts:
        return "HumanIK"
    return "Unknown"
