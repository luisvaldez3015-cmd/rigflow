"""Exception hierarchy.

Every error raised by RigFlow derives from :class:`RigFlowError` and carries an
optional ``hint`` with an actionable suggestion that the UI shows to the user.
"""

from __future__ import annotations

from typing import Optional


class RigFlowError(Exception):
    """Base class for all RigFlow errors."""

    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.hint:
            return "{} ({})".format(self.message, self.hint)
        return self.message


class SceneError(RigFlowError):
    """The Maya scene does not contain what an operation needs."""


class ImportError_(RigFlowError):
    """A file could not be imported or contained nothing usable."""


class UnsupportedError(RigFlowError):
    """The requested operation is not supported for this input."""


class MappingError(RigFlowError):
    """The joint mapping is invalid or incomplete."""


class RetargetError(RigFlowError):
    """The retargeting backend failed."""


class InstallError(RigFlowError):
    """Installation or environment problem."""
