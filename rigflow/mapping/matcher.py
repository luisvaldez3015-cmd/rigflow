"""Automatic joint matching.

Pipeline::

    Skeleton --analyze_names--> NameAnalysis per joint
             --label_topology--> structural roles per joint      (ignored joints excluded)
             --fuse-----------> SkeletonLabeling (role + confidence + evidence per joint)

    SkeletonLabeling (source) + SkeletonLabeling (destination)
             --build_mapping--> JointMapping (one row per role, green/yellow/red)

Both skeletons are labeled independently against the canonical role
vocabulary; the mapping is the join on role. Manual overrides stored in a
previous :class:`JointMapping` survive a recomputation.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from rigflow.core import config
from rigflow.core.logging import get_logger
from rigflow.mapping.model import JointLabel, JointMapping, SkeletonLabeling
from rigflow.skeleton.model import Skeleton
from rigflow.skeleton.naming import NameAnalysis, analyze_names, detect_convention
from rigflow.skeleton.roles import REQUIRED_ROLES, Side, role_part, role_side, sort_roles
from rigflow.skeleton.topology import TopologyResult, label_topology

log = get_logger(__name__)

#: Minimum number of side disagreements before the lateral axis is flipped.
MIN_FLIP_VOTES = 2


def label_skeleton(skeleton: Skeleton, left_is_positive: Optional[bool] = None) -> SkeletonLabeling:
    """Assign a canonical role to every joint using names and topology.

    Args:
        skeleton: The skeleton to label.
        left_is_positive: Force the lateral convention. ``None`` (default)
            guesses Maya's convention and flips it automatically when the joint
            names clearly disagree (characters facing -Z, mirrored imports...).
    """
    analyses = analyze_names(skeleton)
    exclude = {joint for joint, a in analyses.items() if a.ignored}

    guess = True if left_is_positive is None else left_is_positive
    topo = label_topology(skeleton, exclude=exclude, left_is_positive=guess)
    notes: List[str] = []
    if left_is_positive is None and _sides_disagree(analyses, topo):
        topo = label_topology(skeleton, exclude=exclude, left_is_positive=not guess)
        notes.append(
            "Lateral axis flipped: joint names place the left side at negative X "
            "(character facing -Z or mirrored import)."
        )

    labels = {joint: _fuse(joint, analyses[joint], topo) for joint in skeleton.joint_names}
    notes.extend(_resolve_duplicates(labels, skeleton))
    notes.extend(topo.notes)

    labeling = SkeletonLabeling(
        skeleton_name=skeleton.name,
        labels=labels,
        convention=detect_convention(skeleton.joint_names),
        notes=notes,
    )
    log.debug("Labeled %s: %d roles, %d ignored, %d unassigned", skeleton.name,
              len(labeling.roles()), len(labeling.ignored_joints()), len(labeling.unassigned_joints()))
    return labeling


def _sides_disagree(analyses: Dict[str, NameAnalysis], topo: TopologyResult) -> bool:
    agree = disagree = 0
    for joint, role in topo.labels.items():
        topo_side = role_side(role)
        if topo_side is Side.CENTER:
            continue
        analysis = analyses.get(joint)
        if analysis is None or not analysis.side_explicit or analysis.side is Side.CENTER:
            continue
        if analysis.side is topo_side:
            agree += 1
        else:
            disagree += 1
    return disagree > agree and disagree >= MIN_FLIP_VOTES


def _fuse(joint: str, analysis: NameAnalysis, topo: TopologyResult) -> JointLabel:
    if analysis.ignored:
        return JointLabel(joint=joint, ignored=analysis.ignored, notes=["Ignored: {}".format(analysis.ignored)])

    name_role = analysis.role
    topo_role = topo.labels.get(joint)
    topo_conf = topo.confidence.get(joint, 0.0)

    if name_role and topo_role:
        if name_role == topo_role:
            return JointLabel(joint, name_role, config.CONFIDENCE_AGREEMENT, ("name", "topology"))
        if topo_role in analysis.candidate_roles():
            return JointLabel(
                joint, topo_role, config.CONFIDENCE_TOPOLOGY_RESOLVES_AMBIGUITY, ("name", "topology"),
                ["Name '{}' is ambiguous; topology selected {}".format(analysis.joint, topo_role)],
            )
        if role_part(name_role) == role_part(topo_role) and role_side(name_role) is role_side(topo_role):
            # Same chain (Spine vs Spine1...) but different index: trust the explicit name.
            return JointLabel(
                joint, name_role, config.CONFIDENCE_NAME_ONLY_EXPLICIT, ("name", "topology"),
                ["Chain index from name ({}) differs from topology ({})".format(name_role, topo_role)],
            )
        if analysis.confidence >= 0.9:
            return JointLabel(
                joint, name_role, config.CONFIDENCE_CONFLICT_NAME_WINS, ("name",),
                ["Name says {} but topology says {}; review".format(name_role, topo_role)],
            )
        return JointLabel(
            joint, topo_role, config.CONFIDENCE_CONFLICT_TOPOLOGY_WINS, ("topology",),
            ["Topology says {} but name suggests {}; review".format(topo_role, name_role)],
        )

    if name_role:
        conf = (
            config.CONFIDENCE_NAME_ONLY_EXPLICIT
            if analysis.confidence >= 0.9
            else round(analysis.confidence * 0.9, 3)
        )
        return JointLabel(joint, name_role, conf, ("name",))

    if topo_role:
        conf = config.CONFIDENCE_TOPOLOGY_ONLY if topo_conf >= 0.8 else topo_conf
        notes = ["Labeled by hierarchy only"] if topo_conf >= 0.8 else ["Weak structural guess"]
        return JointLabel(joint, topo_role, conf, ("topology",), notes)

    return JointLabel(joint)


def _resolve_duplicates(labels: Dict[str, JointLabel], skeleton: Skeleton) -> List[str]:
    """Keep one joint per role; demote the others to unassigned."""
    notes: List[str] = []
    by_role: Dict[str, List[JointLabel]] = {}
    for label in labels.values():
        if label.role:
            by_role.setdefault(label.role, []).append(label)
    for role, claimants in by_role.items():
        if len(claimants) < 2:
            continue
        claimants.sort(
            key=lambda l: (l.confidence, "topology" in l.evidence, -skeleton.depth(l.joint)),
            reverse=True,
        )
        winner = claimants[0]
        for loser in claimants[1:]:
            loser.notes.append("Role {} also claimed by {} (kept there)".format(role, winner.joint))
            loser.role = None
            loser.confidence = 0.0
            notes.append("{}: {} and {} both looked like {}; kept {}".format(
                role, winner.joint, loser.joint, role, winner.joint))
    return notes


def build_mapping(
    source: SkeletonLabeling,
    destination: SkeletonLabeling,
    previous: Optional[JointMapping] = None,
) -> JointMapping:
    """Join two labelings on role. Manual overrides of ``previous`` are kept."""
    mapping = JointMapping(source.skeleton_name, destination.skeleton_name)
    if previous is not None:
        mapping.manual = dict(previous.manual)
        mapping.manual_sides = {role: set(sides) for role, sides in previous.manual_sides.items()}
        mapping.excluded = set(previous.excluded)

    source_roles = source.roles()
    destination_roles = destination.roles()
    for role in sort_roles(set(source_roles) | set(destination_roles) | set(REQUIRED_ROLES)):
        src_joint = source_roles.get(role)
        dst_joint = destination_roles.get(role)
        notes: List[str] = []
        if src_joint and dst_joint:
            confidence = min(source.confidence_of(src_joint), destination.confidence_of(dst_joint))
            notes += source.labels[src_joint].notes
            notes += destination.labels[dst_joint].notes
        else:
            confidence = 0.0
            if not src_joint and not dst_joint:
                notes.append("Not found on either skeleton")
            elif not src_joint:
                notes.append("Not found on the source skeleton")
            else:
                notes.append("Not found on the destination skeleton")
        mapping.set_auto(role, src_joint, dst_joint, confidence, notes)

    mapping.apply_manual()
    return mapping


def auto_map(
    source_skeleton: Skeleton,
    destination_skeleton: Skeleton,
    previous: Optional[JointMapping] = None,
) -> Tuple[JointMapping, SkeletonLabeling, SkeletonLabeling]:
    """Convenience: label both skeletons and build the mapping in one call."""
    source = label_skeleton(source_skeleton)
    destination = label_skeleton(destination_skeleton)
    return build_mapping(source, destination, previous), source, destination
