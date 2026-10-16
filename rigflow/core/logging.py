"""Structured logging for RigFlow.

Use ``get_logger(__name__)`` in every module. All loggers hang under the
``rigflow`` logger, which gets a single stream handler so messages appear in
Maya's Script Editor (or the console under ``mayapy``) exactly once.
"""

from __future__ import annotations

import logging
import os

ROOT_LOGGER_NAME = "rigflow"
_FORMAT = "[%(name)s] %(levelname)s: %(message)s"
_ENV_LEVEL = "RIGFLOW_LOG_LEVEL"


def _configure_root() -> logging.Logger:
    root = logging.getLogger(ROOT_LOGGER_NAME)
    if not getattr(root, "_rigflow_configured", False):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
        root.propagate = False
        level_name = os.environ.get(_ENV_LEVEL, "INFO").upper()
        root.setLevel(getattr(logging, level_name, logging.INFO))
        root._rigflow_configured = True  # type: ignore[attr-defined]
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under ``rigflow``."""
    _configure_root()
    if name == ROOT_LOGGER_NAME or name.startswith(ROOT_LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger("{}.{}".format(ROOT_LOGGER_NAME, name))


def set_level(level: int) -> None:
    """Set the verbosity of every RigFlow logger."""
    _configure_root().setLevel(level)
