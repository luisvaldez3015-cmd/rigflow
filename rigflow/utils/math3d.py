"""Minimal 3-vector helpers on plain tuples.

Kept dependency-free so the skeleton and mapping packages can run outside
Maya. Heavy matrix work happens in Maya code with ``maya.api.OpenMaya``.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence, Tuple

Vec3 = Tuple[float, float, float]

AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def vec(a: Sequence[float]) -> Vec3:
    return (float(a[0]), float(a[1]), float(a[2]))


def add(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Sequence[float], s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(a: Sequence[float]) -> float:
    return math.sqrt(dot(a, a))


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    return length(sub(a, b))


def normalize(a: Sequence[float]) -> Vec3:
    n = length(a)
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def lerp(a: Sequence[float], b: Sequence[float], t: float) -> Vec3:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def mean(points: Iterable[Sequence[float]]) -> Vec3:
    pts = list(points)
    if not pts:
        return (0.0, 0.0, 0.0)
    n = float(len(pts))
    return (
        sum(p[0] for p in pts) / n,
        sum(p[1] for p in pts) / n,
        sum(p[2] for p in pts) / n,
    )


def component(a: Sequence[float], axis: str) -> float:
    """Return the component of ``a`` along ``'x'``, ``'y'`` or ``'z'``."""
    return float(a[AXIS_INDEX[axis.lower()]])


def dominant_axis(a: Sequence[float]) -> Tuple[str, float]:
    """Return ``(axis_name, sign)`` of the largest-magnitude component."""
    idx = max(range(3), key=lambda i: abs(a[i]))
    sign = 1.0 if a[idx] >= 0 else -1.0
    return ("xyz"[idx], sign)
