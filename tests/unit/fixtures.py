"""In-memory skeletons used by the unit tests.

The specs live in :mod:`rigflow.skeleton.samples` so the UI preview, the demo
scene builder and the tests all describe the same characters. This module
keeps the short constructor names the tests use.
"""

from __future__ import annotations

from rigflow.skeleton.model import Skeleton
from rigflow.skeleton.samples import (  # noqa: F401  (re-exported for the tests)
    Spec,
    advanced_skeleton_spec,
    build_skeleton as build,
    custom_spec,
    mirror as _mirror,
    mixamo_mirrored_spec,
    mixamo_spec,
    nameless_spec,
    unreal_spec,
)


def mixamo(**kwargs) -> Skeleton:
    return build(mixamo_spec(**kwargs), name="mixamo")


def mixamo_mirrored() -> Skeleton:
    return build(mixamo_mirrored_spec(), name="mixamo_mirrored")


def nameless() -> Skeleton:
    return build(nameless_spec(), name="nameless")


def unreal(**kwargs) -> Skeleton:
    return build(unreal_spec(**kwargs), name="unreal")


def advanced_skeleton() -> Skeleton:
    return build(advanced_skeleton_spec(), name="advanced_skeleton")


def custom() -> Skeleton:
    return build(custom_spec(), name="custom")
