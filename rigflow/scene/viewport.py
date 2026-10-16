"""Small Maya UI model-panel adapter used by the Qt interface."""

from __future__ import annotations

from typing import Optional, Sequence

from maya import cmds

from rigflow.core.errors import SceneError, UnsupportedError
from rigflow.core.logging import get_logger
from rigflow.scene.undo import suspended_undo

log = get_logger(__name__)

#: ``panel -> paneLayout`` for panels RigFlow created. Panels parented to a Qt
#: layout have no window path, so the pane name is recorded at creation time
#: instead of being rebuilt from ``modelPanel -q -parent``.
_PANES = {}


def _require_ui() -> None:
    if cmds.about(batch=True):
        raise UnsupportedError("Viewport previews need the Maya UI",
                               hint="Open RigFlow inside an interactive Maya session.")


def create_model_panel(parent_name: str, camera: str = "persp",
                       isolate: Sequence[str] = ()) -> str:
    """Create a shaded panel in a pane layout under the given Maya UI parent."""
    _require_ui()
    pane = None
    previous_parent = cmds.setParent(query=True)
    try:
        # Viewport management must never touch the user's undo queue.
        with suspended_undo():
            cmds.setParent(parent_name)
            pane = cmds.paneLayout()
            panel = cmds.modelPanel(menuBarVisible=False, camera=camera)
            _PANES[panel] = pane
            cmds.modelPanel(panel, edit=True, menuBarVisible=False)
            cmds.modelEditor(panel, edit=True, displayAppearance="smoothShaded", grid=True,
                             hud=False, joints=True, nurbsCurves=False, polymeshes=True,
                             locators=False, cameras=False, lights=False)
            if isolate:
                previous = cmds.ls(selection=True, long=True) or []
                try:
                    cmds.select(list(isolate), replace=True)
                    cmds.isolateSelect(panel, state=True)
                    cmds.isolateSelect(panel, addSelected=True)
                finally:
                    cmds.select(previous, replace=True) if previous else cmds.select(clear=True)
            return panel
    except RuntimeError as exc:
        if pane and cmds.paneLayout(pane, exists=True):
            cmds.deleteUI(pane)
        raise SceneError("Could not create viewport: {}".format(exc),
                         hint="Use an existing Maya UI layout and camera.") from exc
    finally:
        if previous_parent:
            cmds.setParent(previous_parent)


def panel_container(panel: str) -> Optional[str]:
    """Return the private pane layout that hosts ``panel`` (the widget to embed)."""
    _require_ui()
    pane = _PANES.get(panel)
    if pane and cmds.paneLayout(pane, exists=True):
        return pane
    if not cmds.modelPanel(panel, exists=True):
        return None
    parent = cmds.modelPanel(panel, query=True, parent=True)
    return parent if parent and cmds.paneLayout(parent, exists=True) else None


def delete_model_panel(panel: str) -> None:
    """Delete the embedded panel and its private pane layout if still present."""
    _require_ui()
    pane = panel_container(panel)
    _PANES.pop(panel, None)
    with suspended_undo():
        if cmds.modelPanel(panel, exists=True):
            cmds.deleteUI(panel, panel=True)
        if pane and cmds.paneLayout(pane, exists=True):
            cmds.deleteUI(pane)


def frame_nodes(panel: str, nodes: Sequence[str]) -> None:
    """Frame DAG content in the panel while preserving the user's selection."""
    _require_ui()
    if not cmds.modelPanel(panel, exists=True):
        raise SceneError("Viewport panel does not exist: {}".format(panel),
                         hint="Reopen the viewport preview.")
    targets = cmds.ls(list(nodes), dagObjects=True, long=True) if nodes else []
    if not targets:
        return
    with suspended_undo():
        previous = cmds.ls(selection=True, long=True) or []
        try:
            cmds.select(targets, replace=True)
            camera = cmds.modelPanel(panel, query=True, camera=True)
            cmds.viewFit(camera, fitFactor=0.9)  # fits the current selection
        finally:
            cmds.select(previous, replace=True) if previous else cmds.select(clear=True)
        cmds.refresh(force=True)


def refresh() -> None:
    """Force every view to repaint (used after embedding or re-parenting panels)."""
    if not cmds.about(batch=True):
        cmds.refresh(force=True)
