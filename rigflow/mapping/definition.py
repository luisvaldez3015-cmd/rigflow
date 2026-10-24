"""Pure queries shared by character-definition widgets and controllers."""
from rigflow.core.config import GREEN_THRESHOLD
from rigflow.skeleton.roles import REQUIRED_ROLES


def joint_for(mapping, role, side):
    match = mapping.matches.get(role) if mapping else None
    return getattr(match, side) if match else None


def progress(mapping, side, skeleton):
    """Count required slots containing joints that still belong to this model."""
    return sum(joint_for(mapping, role, side) in skeleton for role in REQUIRED_ROLES) if skeleton else 0


def slot_state(mapping, role, side, skeleton, labeling=None):
    joint = joint_for(mapping, role, side)
    if not joint:
        return "required" if role in REQUIRED_ROLES else "empty"
    match = mapping.matches[role]
    if joint not in skeleton or match.excluded:
        return "invalid"
    if any(m.role != role and getattr(m, side) == joint for m in mapping.matches.values()):
        return "invalid"
    manual = role in mapping.manual and side in mapping.manual_sides.get(role, {"source", "destination"})
    confidence = labeling.confidence_of(joint) if labeling else match.confidence
    return "assigned" if manual or confidence >= GREEN_THRESHOLD else "review"
