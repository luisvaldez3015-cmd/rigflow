"""Animation transfer backends for Maya skeletons."""

from __future__ import annotations

from typing import List, Optional, Tuple

from rigflow.core.errors import UnsupportedError

from .base import RetargetRequest, RetargetResult, Retargeter
from .hik import HumanIKRetargeter
from .matrix import MatrixRetargeter

__all__ = ["RetargetRequest", "RetargetResult", "Retargeter", "HumanIKRetargeter",
           "MatrixRetargeter", "available_backends", "get_retargeter"]


def available_backends() -> List[Tuple[str, bool, str]]:
    """List the preferred HIK backend and the matrix fallback with reasons."""
    return [(backend.name,) + backend.availability()
            for backend in (HumanIKRetargeter, MatrixRetargeter)]


def get_retargeter(preferred: Optional[str] = None) -> Retargeter:
    """Choose HIK by default, or honour an explicitly requested backend."""
    for backend in (HumanIKRetargeter, MatrixRetargeter):
        if preferred is not None and preferred != backend.name:
            continue
        available, reason = backend.availability()
        if available:
            return backend()
        if preferred:
            raise UnsupportedError(reason, hint="choose the matrix fallback")
    raise UnsupportedError("Unknown or unavailable retarget backend: " + str(preferred),
                           hint="choose humanik or matrix")
