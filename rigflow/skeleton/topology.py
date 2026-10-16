"""Role inference from hierarchy topology and rest-pose positions.

Works on a :class:`~rigflow.skeleton.model.Skeleton` without looking at any
joint name, so it labels numbered or foreign-language skeletons and acts as an
independent witness that confirms or contradicts the naming analysis.

Assumptions (all explicit, all reported in ``notes`` when violated):

* The character is roughly upright in its rest pose along ``skeleton.up_axis``.
* Left/right are separated along the lateral axis (``x`` by default) and, by
  Maya convention, the character's **left** side is at **positive** X. The
  caller can flip this; :mod:`rigflow.mapping.matcher` does so automatically
  when joint names disagree with the geometric guess.
* The hips are the first joint (walking down from the root) with two
  downward branches (legs) and one upward branch (spine).
* The chest is the first spine joint whose branches spread to both sides (arms).

Joints listed in ``exclude`` (typically end tips, twist helpers and facial
joints identified by the naming analysis) are invisible to the walk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from rigflow.core.config import (
    MAX_CHAIN_JOINTS,
    MAX_HIPS_SEARCH_DEPTH,
    SIGNIFICANT_BRANCH_MIN_JOINTS,
)
from rigflow.skeleton.model import Skeleton
from rigflow.skeleton.roles import Side, role_name

CONF_STRUCTURE_CLEAR = 0.85
CONF_HIPS = 0.9
CONF_HEAD = 0.7
CONF_FALLBACK = 0.55
CONF_WEAK = 0.4
#: Lateral offset (fraction of skeleton height) above which a branch counts as
#: going sideways (an arm) instead of straight up (the neck).
LATERAL_BRANCH_FRACTION = 0.02


@dataclass
class TopologyResult:
    labels: Dict[str, str] = field(default_factory=dict)
    confidence: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    hips: Optional[str] = None
    chest: Optional[str] = None
    left_is_positive: bool = True

    def role_of(self, joint: str) -> Optional[str]:
        return self.labels.get(joint)

    def joint_for(self, role: str) -> Optional[str]:
        for joint, assigned in self.labels.items():
            if assigned == role:
                return joint
        return None


def label_topology(
    skeleton: Skeleton,
    exclude: Iterable[str] = (),
    left_is_positive: bool = True,
    lateral_axis: str = "x",
) -> TopologyResult:
    """Label a skeleton's joints by structure alone. Never raises on odd input."""
    analyzer = _TopologyAnalyzer(skeleton, set(exclude), left_is_positive, lateral_axis)
    return analyzer.run()


class _TopologyAnalyzer:
    def __init__(self, skeleton: Skeleton, exclude: set, left_is_positive: bool, lateral_axis: str):
        self.skel = skeleton
        self.exclude = exclude
        self.left_is_positive = left_is_positive
        self.lateral_axis = lateral_axis
        self.result = TopologyResult(left_is_positive=left_is_positive)
        self._size_cache: Dict[str, int] = {}
        self._mean_cache: Dict[str, tuple] = {}
        height = skeleton.height()
        self.lateral_threshold = max(height * LATERAL_BRANCH_FRACTION, 1e-6)

    # --- helpers ---------------------------------------------------------------------

    def kids(self, joint: str) -> List[str]:
        return [c for c in self.skel.children(joint) if c not in self.exclude]

    def size(self, joint: str) -> int:
        if joint not in self._size_cache:
            self._size_cache[joint] = 1 + sum(self.size(c) for c in self.kids(joint))
        return self._size_cache[joint]

    def significant(self, joint: str) -> List[str]:
        return [c for c in self.kids(joint) if self.size(c) >= SIGNIFICANT_BRANCH_MIN_JOINTS]

    def subtree_mean(self, joint: str) -> tuple:
        """Mean up/lateral coordinates of a subtree (inclusive)."""
        if joint not in self._mean_cache:
            nodes = [joint] + [d for d in self.skel.descendants(joint) if d not in self.exclude]
            ups = [self.skel.up(n) for n in nodes]
            lats = [self.skel.lateral(n, self.lateral_axis) for n in nodes]
            self._mean_cache[joint] = (sum(ups) / len(ups), sum(lats) / len(lats))
        return self._mean_cache[joint]

    def vertical_offset(self, parent: str, child: str) -> float:
        return self.subtree_mean(child)[0] - self.skel.up(parent)

    def lateral_offset(self, parent: str, child: str) -> float:
        return self.subtree_mean(child)[1] - self.skel.lateral(parent, self.lateral_axis)

    def side_of_offset(self, offset: float) -> Side:
        positive = offset > 0
        if self.left_is_positive:
            return Side.LEFT if positive else Side.RIGHT
        return Side.RIGHT if positive else Side.LEFT

    def note(self, text: str) -> None:
        self.result.notes.append(text)

    def label(self, joint: str, role: str, confidence: float) -> None:
        existing = self.result.labels.get(joint)
        if existing is not None and existing != role:
            if self.result.confidence.get(joint, 0.0) >= confidence:
                self.note("{} already labeled {}; ignoring {}".format(joint, existing, role))
                return
            self.note("{} relabeled from {} to {}".format(joint, existing, role))
        self.result.labels[joint] = role
        self.result.confidence[joint] = confidence

    def walk_chain(self, start: str, stop_at_hand: bool = False) -> List[str]:
        """Follow the main chain from ``start`` (largest subtree at each step)."""
        chain = [start]
        current = start
        for _ in range(64):
            kids = self.kids(current)
            if not kids:
                break
            if stop_at_hand and (len(kids) >= 3 or (len(kids) == 2 and len(chain) >= 3)):
                break
            nxt = max(kids, key=self.size)
            chain.append(nxt)
            current = nxt
        return chain

    # --- main algorithm --------------------------------------------------------------

    def run(self) -> TopologyResult:
        if len(self.skel) == 0:
            self.note("Skeleton is empty")
            return self.result
        roots = [r for r in self.skel.roots if r not in self.exclude]
        if not roots:
            self.note("All joints are excluded")
            return self.result
        root = max(roots, key=self.size)
        if len(roots) > 1:
            self.note("Multiple roots; using the largest hierarchy under {}".format(root))

        hips_info = self.find_hips(root)
        if hips_info is None:
            self.note("Could not identify the hips: no joint with leg and spine branches")
            return self.result
        hips, legs, spine_branches, hips_conf = hips_info
        self.result.hips = hips
        self.label(hips, "Hips", hips_conf)

        self.label_legs(legs)
        if spine_branches:
            self.label_upper_body(spine_branches)
        else:
            self.note("No upward branch from the hips: spine, arms and head not labeled")
        return self.result

    def find_hips(self, root: str):
        current = root
        for _ in range(MAX_HIPS_SEARCH_DEPTH + 1):
            significant = self.significant(current)
            downs = [c for c in significant if self.vertical_offset(current, c) < 0]
            ups = [c for c in significant if self.vertical_offset(current, c) >= 0]

            if len(downs) >= 2 and ups:
                return current, downs, ups, CONF_HIPS
            if len(downs) == 1 and ups:
                legs_root = downs[0]
                sub_downs = [
                    c for c in self.significant(legs_root) if self.vertical_offset(legs_root, c) < 0
                ]
                if len(sub_downs) >= 2:
                    self.note(
                        "Legs branch from {} below the hips {}".format(legs_root, current)
                    )
                    return current, sub_downs, ups, CONF_STRUCTURE_CLEAR
                self.note("Only one leg branch found under {}".format(current))
                return current, downs, ups, CONF_FALLBACK
            if len(downs) >= 2 and not ups:
                self.note("Hips candidate {} has legs but no spine branch".format(current))
                return current, downs, [], CONF_FALLBACK

            candidates = significant or self.kids(current)
            if not candidates:
                return None
            current = max(candidates, key=self.size)
        return None

    def label_legs(self, legs: List[str]) -> None:
        legs = sorted(legs, key=self.size, reverse=True)
        if len(legs) > 2:
            self.note("Extra downward branches from the hips ignored: {}".format(legs[2:]))
            legs = legs[:2]
        hips = self.result.hips
        offsets = {leg: self.lateral_offset(hips, leg) for leg in legs}  # type: ignore[arg-type]
        if len(legs) == 2 and abs(offsets[legs[0]] - offsets[legs[1]]) < 1e-9:
            self.note("Legs have the same lateral position; sides are a guess")
            sides = {legs[0]: Side.LEFT, legs[1]: Side.RIGHT}
            conf = CONF_WEAK
        elif len(legs) == 2:
            first_is_left = offsets[legs[0]] > offsets[legs[1]]
            if not self.left_is_positive:
                first_is_left = not first_is_left
            sides = {
                legs[0]: Side.LEFT if first_is_left else Side.RIGHT,
                legs[1]: Side.RIGHT if first_is_left else Side.LEFT,
            }
            conf = CONF_STRUCTURE_CLEAR
        else:
            sides = {legs[0]: self.side_of_offset(offsets[legs[0]])}
            conf = CONF_FALLBACK

        parts = ("UpLeg", "Leg", "Foot", "ToeBase")
        for leg in legs:
            chain = self.walk_chain(leg)
            chain_conf = conf if len(chain) >= 3 else CONF_FALLBACK
            for part, joint in zip(parts, chain):
                self.label(joint, role_name(part, sides[leg]), chain_conf)
            if len(chain) > len(parts):
                self.note("Leg chain from {} has extra joints past the toe: {}".format(leg, chain[4:]))

    def label_upper_body(self, spine_branches: List[str]) -> None:
        spine_branches = sorted(spine_branches, key=self.size, reverse=True)
        if len(spine_branches) > 1:
            self.note("Extra upward branches from the hips ignored: {}".format(spine_branches[1:]))
        start = spine_branches[0]

        chain = [start]
        current = start
        chest: Optional[str] = None
        lefts: List[str] = []
        rights: List[str] = []
        for _ in range(MAX_CHAIN_JOINTS + 4):
            significant = self.significant(current)
            lefts = [c for c in significant if self.lateral_offset(current, c) > self.lateral_threshold]
            rights = [c for c in significant if self.lateral_offset(current, c) < -self.lateral_threshold]
            if lefts and rights:
                chest = current
                break
            candidates = significant or self.kids(current)
            if not candidates:
                break
            nxt = min(candidates, key=lambda c: (abs(self.lateral_offset(current, c)), -self.size(c)))
            chain.append(nxt)
            current = nxt

        if chest is None:
            self.label_spine_without_arms(chain)
            return

        self.result.chest = chest
        spine_chain = chain
        if len(spine_chain) > MAX_CHAIN_JOINTS:
            self.note("Spine chain longer than {} joints; extras unlabeled".format(MAX_CHAIN_JOINTS))
        for i, joint in enumerate(spine_chain[:MAX_CHAIN_JOINTS]):
            self.label(joint, role_name("Spine", index=i), CONF_STRUCTURE_CLEAR)

        if not self.left_is_positive:
            lefts, rights = rights, lefts
        self.label_arm(lefts, Side.LEFT)
        self.label_arm(rights, Side.RIGHT)

        central = [
            c for c in self.kids(chest)
            if c not in lefts and c not in rights and self.vertical_offset(chest, c) > 0
        ]
        if not central:
            self.note("No neck/head branch found above the chest {}".format(chest))
            return
        neck_start = min(central, key=lambda c: (abs(self.lateral_offset(chest, c)), -self.size(c)))
        self.label_neck_and_head(neck_start)

    def label_spine_without_arms(self, chain: List[str]) -> None:
        self.note("No arm branches found; spine/neck/head labeled by order only")
        if len(chain) >= 3:
            spine, neck, head = chain[:-2], chain[-2], chain[-1]
        elif len(chain) == 2:
            spine, neck, head = chain[:1], None, chain[1]
        else:
            spine, neck, head = chain, None, None
        for i, joint in enumerate(spine[:MAX_CHAIN_JOINTS]):
            self.label(joint, role_name("Spine", index=i), CONF_WEAK)
        if neck:
            self.label(neck, "Neck", CONF_WEAK)
        if head:
            self.label(head, "Head", CONF_WEAK)

    def label_arm(self, branches: List[str], side: Side) -> None:
        if not branches:
            self.note("No {} arm branch found".format(side.value))
            return
        branches = sorted(branches, key=self.size, reverse=True)
        if len(branches) > 1:
            self.note("Extra {} branches from the chest ignored: {}".format(side.value, branches[1:]))
        chain = self.walk_chain(branches[0], stop_at_hand=True)
        parts_from_hand = ("Hand", "ForeArm", "Arm", "Shoulder")
        conf = CONF_STRUCTURE_CLEAR if 3 <= len(chain) <= 4 else CONF_FALLBACK
        for part, joint in zip(parts_from_hand, reversed(chain)):
            self.label(joint, role_name(part, side), conf)
        if len(chain) > len(parts_from_hand):
            self.note(
                "{} arm chain has extra joints between chest and shoulder: {}".format(
                    side.value, chain[: len(chain) - len(parts_from_hand)]
                )
            )

    def label_neck_and_head(self, neck_start: str) -> None:
        chain = self.walk_chain(neck_start)
        if len(chain) == 1:
            self.label(chain[0], "Head", CONF_HEAD)
            self.note("No neck joint between chest and head")
            return
        neck_chain, head = chain[:-1], chain[-1]
        if len(neck_chain) > MAX_CHAIN_JOINTS:
            self.note("Neck chain longer than {} joints; extras unlabeled".format(MAX_CHAIN_JOINTS))
        for i, joint in enumerate(neck_chain[:MAX_CHAIN_JOINTS]):
            self.label(joint, role_name("Neck", index=i), CONF_STRUCTURE_CLEAR)
        self.label(head, "Head", CONF_HEAD)
