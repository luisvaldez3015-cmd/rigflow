"""RigFlow's optional Qt interface. Importing this package does not load Qt."""
from __future__ import annotations


def show(dev_reload=False):
    """Open the singleton Maya panel (or a standalone preview window)."""
    from rigflow.ui.launcher import show as launch
    return launch(dev_reload=dev_reload)
