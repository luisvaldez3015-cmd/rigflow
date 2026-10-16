"""String helpers for Maya node names."""

from __future__ import annotations

import re
from typing import List

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_DIGIT_BOUNDARY = re.compile(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")
_SEPARATORS = re.compile(r"[^A-Za-z0-9]+")
_NUMBER = re.compile(r"\d+")


def short_name(name: str) -> str:
    """Return the leaf name of a DAG path without namespaces.

    ``"|grp|mixamorig:LeftArm"`` becomes ``"LeftArm"``.
    """
    leaf = name.rsplit("|", 1)[-1]
    return leaf.rsplit(":", 1)[-1]


def namespace_of(name: str) -> str:
    """Return the namespace part of a node name (``""`` when absent)."""
    leaf = name.rsplit("|", 1)[-1]
    if ":" in leaf:
        return leaf.rsplit(":", 1)[0]
    return ""


def split_tokens(name: str) -> List[str]:
    """Split a node name into lowercase tokens.

    Splits on separators (``_``, spaces, ``-``, ``.``), on camelCase
    boundaries and between letters and digits::

        "LeftHandIndex1"  -> ["left", "hand", "index", "1"]
        "upperarm_twist_01_l" -> ["upperarm", "twist", "01", "l"]
        "Bip01 L Thigh" -> ["bip", "01", "l", "thigh"]
    """
    text = short_name(name)
    text = _SEPARATORS.sub(" ", text)
    text = _CAMEL_BOUNDARY.sub(" ", text)
    text = _DIGIT_BOUNDARY.sub(" ", text)
    return [t.lower() for t in text.split() if t]


def natural_key(name: str):
    """Sort key that orders ``spine_2`` before ``spine_10``."""
    return [int(p) if p.isdigit() else p.lower() for p in _NUMBER.split(name) + _NUMBER.findall(name)]


def is_number(token: str) -> bool:
    return token.isdigit()
