"""Undo helpers.

Every RigFlow operation that modifies the scene runs inside :func:`undo_chunk`
so that a single Ctrl+Z reverts the whole operation (import, characterise,
bake...) instead of one internal step at a time.
"""

from __future__ import annotations

import functools
from contextlib import contextmanager
from typing import Callable, Iterator

from maya import cmds

from rigflow.core.logging import get_logger

log = get_logger(__name__)


@contextmanager
def undo_chunk(name: str = "RigFlow") -> Iterator[None]:
    """Group every scene change inside the block into one undo step."""
    cmds.undoInfo(openChunk=True, chunkName=name)
    try:
        yield
    finally:
        cmds.undoInfo(closeChunk=True)


def undoable(name: str = None) -> Callable:
    """Decorator form of :func:`undo_chunk`."""

    def decorator(func: Callable) -> Callable:
        chunk_name = name or "RigFlow: {}".format(func.__name__)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with undo_chunk(chunk_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def suspended_undo() -> Iterator[None]:
    """Temporarily disable undo recording (for throw-away scratch operations)."""
    state = cmds.undoInfo(q=True, state=True)
    cmds.undoInfo(stateWithoutFlush=False)
    try:
        yield
    finally:
        cmds.undoInfo(stateWithoutFlush=state)
