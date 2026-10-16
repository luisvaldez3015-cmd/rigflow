"""Consistency checks for a joint mapping before preview or transfer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from rigflow.core import config
from rigflow.mapping.model import JointMapping, MatchStatus
from rigflow.skeleton.model import Skeleton
from rigflow.skeleton.roles import (
    CHAIN_PARTS,
    FINGER_PARTS,
    REQUIRED_ROLES,
    Side,
    role_part,
    role_side,
    template_ancestor_parts,
)

ERROR = "error"
WARNING = "warning"


@dataclass
class ValidationIssue:
    level: str
    message: str
    role: Optional[str] = None

    def __str__(self) -> str:
        prefix = "[{}]".format(self.level.upper())
        if self.role:
            return "{} {}: {}".format(prefix, self.role, self.message)
        return "{} {}".format(prefix, self.message)


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.level == ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.level == WARNING]

    def add(self, level: str, message: str, role: Optional[str] = None) -> None:
        self.issues.append(ValidationIssue(level, message, role))


def validate_mapping(
    mapping: JointMapping,
    source: Optional[Skeleton] = None,
    destination: Optional[Skeleton] = None,
) -> ValidationReport:
    """Validate a mapping. Errors block the transfer; warnings are shown."""
    report = ValidationReport()
    _check_required(mapping, report)
    _check_duplicates(mapping, report)
    _check_low_confidence(mapping, report)
    if source is not None:
        _check_hierarchy(mapping, source, "source", report)
    if destination is not None:
        _check_hierarchy(mapping, destination, "destination", report)
    if source is not None and destination is not None:
        _check_scale(source, destination, report)
    return report


def _check_required(mapping: JointMapping, report: ValidationReport) -> None:
    for role in REQUIRED_ROLES:
        match = mapping.matches.get(role)
        if match is None or not match.complete:
            missing = []
            if match is None or match.source is None:
                missing.append("source")
            if match is None or match.destination is None:
                missing.append("destination")
            report.add(ERROR, "Required joint not mapped on the {}".format(" and ".join(missing)), role)
        elif match.excluded:
            report.add(ERROR, "Required joint cannot be excluded from the transfer", role)


def _check_duplicates(mapping: JointMapping, report: ValidationReport) -> None:
    for side_name in ("source", "destination"):
        seen: Dict[str, str] = {}
        for match in mapping.sorted_matches():
            joint = getattr(match, side_name)
            if not joint or match.excluded:
                continue
            if joint in seen:
                report.add(
                    ERROR,
                    "{} joint '{}' is used by both {} and {}".format(
                        side_name.capitalize(), joint, seen[joint], match.role
                    ),
                    match.role,
                )
            else:
                seen[joint] = match.role


def _check_low_confidence(mapping: JointMapping, report: ValidationReport) -> None:
    for match in mapping.sorted_matches():
        if match.complete and match.status is MatchStatus.RED:
            report.add(WARNING, "Low-confidence match; confirm it manually", match.role)
        elif match.status is MatchStatus.YELLOW:
            report.add(WARNING, "Match needs review", match.role)


def _check_hierarchy(mapping: JointMapping, skeleton: Skeleton, side_name: str, report: ValidationReport) -> None:
    """The nearest mapped ancestor of each joint must be a template ancestor."""
    joint_to_role = {
        getattr(m, side_name): m.role
        for m in mapping.matches.values()
        if getattr(m, side_name) and not m.excluded
    }
    for joint, role in joint_to_role.items():
        if joint not in skeleton:
            report.add(ERROR, "{} joint '{}' does not exist in the skeleton".format(
                side_name.capitalize(), joint), role)
            continue
        part = role_part(role)
        if part is None or part == "Hips":
            continue
        expected = set(template_ancestor_parts(part))
        for ancestor in skeleton.ancestors(joint):
            ancestor_role = joint_to_role.get(ancestor)
            if ancestor_role is None:
                continue
            ancestor_part = role_part(ancestor_role)
            # Spine/neck chains and finger phalanges legitimately hang under the same part.
            same_chain = (part in CHAIN_PARTS or part in FINGER_PARTS) and ancestor_part == part
            side_ok = role_side(ancestor_role) in (Side.CENTER, role_side(role))
            if (ancestor_part in expected or same_chain) and side_ok:
                break
            report.add(
                WARNING,
                "{} joint '{}' hangs under {} ('{}'), which is not an expected parent".format(
                    side_name.capitalize(), joint, ancestor_role, ancestor
                ),
                role,
            )
            break


def _check_scale(source: Skeleton, destination: Skeleton, report: ValidationReport) -> None:
    src_h, dst_h = source.height(), destination.height()
    if src_h <= 0 or dst_h <= 0:
        report.add(WARNING, "Could not measure skeleton height; root motion scale may be wrong")
        return
    ratio = dst_h / src_h
    if ratio < config.SUSPICIOUS_SCALE_RATIO_MIN or ratio > config.SUSPICIOUS_SCALE_RATIO_MAX:
        report.add(
            WARNING,
            "Destination is {:.2f}x the source height; check scene units (cm vs m)".format(ratio),
        )
