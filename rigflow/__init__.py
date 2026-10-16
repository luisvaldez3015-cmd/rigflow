"""RigFlow — Animation Transfer for Maya.

Public entry points:

* :data:`__version__` — package version string.
* :func:`launch` — open the main window inside Maya (lazy import of the UI).

Everything under :mod:`rigflow.skeleton`, :mod:`rigflow.mapping`,
:mod:`rigflow.core` and :mod:`rigflow.utils` is pure Python and importable
outside Maya. Maya-dependent code lives in :mod:`rigflow.scene`,
:mod:`rigflow.retargeting`, :mod:`rigflow.animation` and :mod:`rigflow.ui`.
"""

from __future__ import annotations

__version__ = "0.1.0.dev0"
__all__ = ["__version__", "launch"]


def launch(dev_reload: bool = False):
    """Open (or raise) the RigFlow main window inside Maya.

    Args:
        dev_reload: When True, reload all ``rigflow`` modules before opening.
            Intended for development only.

    Returns:
        The main window instance.
    """
    if dev_reload:
        from rigflow.core.compat import reload_package

        reload_package()
    from rigflow.ui.launcher import show

    return show()
