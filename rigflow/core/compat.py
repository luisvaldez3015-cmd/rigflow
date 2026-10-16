"""Environment and compatibility detection.

Centralises every "which Maya / which Python / which Qt" question so the rest
of the code never sprinkles version checks. Safe to import outside Maya.
"""

from __future__ import annotations

import importlib
import sys
from typing import Optional

#: Maya versions RigFlow is developed and tested against on this machine.
TESTED_MAYA_VERSIONS = (2023, 2024)
#: Oldest Maya version the code is written to support (Python 3.9+).
MIN_MAYA_VERSION = 2023


def in_maya() -> bool:
    """True when ``maya.cmds`` is importable *and* initialised.

    Under plain ``mayapy`` the module imports but commands fail until
    ``maya.standalone.initialize()`` is called; that counts as *not* in Maya.
    """
    try:
        import maya.cmds as cmds  # noqa: WPS433 (runtime import on purpose)

        cmds.about(version=True)
        return True
    except Exception:  # pragma: no cover - depends on environment
        return False


def maya_version() -> Optional[int]:
    """Return the Maya major version (e.g. ``2024``) or ``None`` outside Maya."""
    if not in_maya():
        return None
    import maya.cmds as cmds

    try:
        return int(str(cmds.about(version=True)).split(".")[0].split()[0])
    except (ValueError, IndexError):  # pragma: no cover - defensive
        return None


def is_batch() -> bool:
    """True in ``mayapy``/batch mode where there is no UI."""
    if not in_maya():
        return True
    import maya.cmds as cmds

    return bool(cmds.about(batch=True))


def python_version() -> str:
    return "{}.{}.{}".format(*sys.version_info[:3])


def qt_binding() -> Optional[str]:
    """Name of the available Qt binding without importing the whole UI."""
    for name in ("PySide6", "PySide2"):
        if importlib.util.find_spec(name) is not None:
            return name
    return None


def environment_summary() -> dict:
    """Human-readable snapshot used by the About dialog and bug reports."""
    return {
        "rigflow": _package_version(),
        "maya": maya_version(),
        "batch": is_batch(),
        "python": python_version(),
        "qt_binding": qt_binding(),
        "platform": sys.platform,
    }


def _package_version() -> str:
    from rigflow import __version__

    return __version__


def reload_package(prefix: str = "rigflow") -> int:
    """Reload every imported ``rigflow`` module (development helper).

    Modules are reloaded leaf-first so that parents see refreshed children.
    Returns the number of modules reloaded.
    """
    names = sorted(
        (n for n in sys.modules if n == prefix or n.startswith(prefix + ".")),
        key=lambda n: n.count("."),
        reverse=True,
    )
    count = 0
    for name in names:
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)
            count += 1
    return count
