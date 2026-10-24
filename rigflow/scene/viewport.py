"""Small Maya UI model-panel adapter used by the Qt interface."""

from __future__ import annotations

from typing import Optional, Sequence
from dataclasses import dataclass

from maya import cmds

from rigflow.core.errors import SceneError, UnsupportedError
from rigflow.core.logging import get_logger
from rigflow.scene.undo import suspended_undo

log = get_logger(__name__)


def main_model_panel():
    """Find an artist panel, excluding the embedded panels owned by RigFlow."""
    _require_ui()
    panels = cmds.getPanel(type="modelPanel") or []
    focused = cmds.getPanel(withFocus=True)
    visible = cmds.getPanel(visiblePanels=True) or []
    for panel in [focused] + visible + panels:
        if panel in panels and panel not in _PANES:
            return panel
    raise SceneError("No main Maya model panel available.", hint="Open a Maya perspective viewport.")


def definition_nodes(nodes):
    """Expand only joints and non-intermediate mesh transforms for isolation."""
    dag = cmds.ls(list(nodes), dagObjects=True, long=True) or [] if nodes else []
    targets = [n for n in dag if cmds.nodeType(n) == "joint"]
    for shape in cmds.ls(dag, type="mesh", long=True) or [] if dag else []:
        if not cmds.getAttr(shape + ".intermediateObject"):
            targets.extend(cmds.listRelatives(shape, parent=True, fullPath=True) or [])
    return list(dict.fromkeys(targets))


def _isolate_set(panel):
    cmds.isolateSelect(panel, state=True)
    view_set = cmds.isolateSelect(panel, query=True, viewObjects=True)
    # A new scene can retain the panel's isolate flag after its set was deleted.
    if not view_set or not cmds.objExists(view_set):
        cmds.isolateSelect(panel, state=False)
        cmds.isolateSelect(panel, state=True)
        # Maya creates the set lazily, on its first addSelected. Seed it with
        # an existing DAG node; the caller immediately replaces all members.
        previous = cmds.ls(selection=True, long=True) or []
        try:
            cmds.select(cmds.modelPanel(panel, query=True, camera=True), replace=True)
            cmds.isolateSelect(panel, addSelected=True)
        finally:
            cmds.select(previous, replace=True) if previous else cmds.select(clear=True)
        view_set = cmds.isolateSelect(panel, query=True, viewObjects=True)
    if not view_set:
        raise SceneError("Maya could not initialise viewport isolation.", hint="Reopen the main model panel.")
    return view_set


@dataclass
class DefinitionViewport:
    """Reversible lease of the main model panel; never changes node visibility."""
    panel: str
    isolated: bool
    members: list
    flags: dict
    camera: str
    matrix: list
    camera_values: dict
    active_nodes: tuple = ()
    restored: bool = False

    @classmethod
    def capture(cls, panel=None):
        _require_ui()
        panel = panel or main_model_panel()
        view_set = cmds.isolateSelect(panel, query=True, viewObjects=True)
        camera = cmds.modelPanel(panel, query=True, camera=True)
        camera = (cmds.listRelatives(camera, parent=True, fullPath=True) or [camera])[0] if cmds.nodeType(camera) == "camera" else camera
        shape = (cmds.listRelatives(camera, shapes=True, type="camera", fullPath=True) or [camera])[0]
        return cls(panel, bool(cmds.isolateSelect(panel, query=True, state=True)),
                   cmds.sets(view_set, query=True) or [] if view_set else [],
                   {flag: cmds.modelEditor(panel, query=True, **{flag: True})
                    for flag in ("jointXray", "joints", "polymeshes")}, camera,
                   cmds.xform(camera, query=True, objectSpace=True, matrix=True),
                   {shape + "." + attr: cmds.getAttr(shape + "." + attr)
                    for attr in ("centerOfInterest", "orthographicWidth")})

    def show(self, nodes, display="Both"):
        _require_ui()
        if display not in ("Bones", "Mesh", "Both"):
            raise ValueError("Unknown definition display: " + display)
        if self.restored or not cmds.modelPanel(self.panel, exists=True):
            return
        nodes = tuple(nodes)
        with suspended_undo():
            cmds.modelEditor(self.panel, edit=True, jointXray=True,
                             joints=display != "Mesh", polymeshes=display != "Bones")
            if nodes != self.active_nodes:
                # Explicit joints and visible mesh transforms omit controls/helpers.
                targets = definition_nodes(nodes)
                view_set = _isolate_set(self.panel)
                cmds.sets(clear=view_set)
                if targets:
                    cmds.sets(list(dict.fromkeys(targets)), addElement=view_set)
                cmds.isolateSelect(self.panel, update=True)
                frame_nodes(self.panel, targets)
                self.active_nodes = nodes

    def restore(self):
        """Restore isolate members, display flags and the framing camera exactly once."""
        if self.restored:
            return
        if not cmds.modelPanel(self.panel, exists=True):
            self.restored = True
            return
        with suspended_undo():
            cmds.modelEditor(self.panel, edit=True, **self.flags)
            view_set = _isolate_set(self.panel)
            cmds.sets(clear=view_set)
            members = [n for n in self.members if cmds.objExists(n)]
            if members:
                cmds.sets(members, addElement=view_set)
            cmds.isolateSelect(self.panel, update=True)
            cmds.isolateSelect(self.panel, state=self.isolated)
            if cmds.objExists(self.camera):
                cmds.modelPanel(self.panel, edit=True, camera=self.camera)
                cmds.xform(self.camera, objectSpace=True, matrix=self.matrix)
                for plug, value in self.camera_values.items():
                    if cmds.objExists(plug) and not cmds.getAttr(plug, lock=True):
                        cmds.setAttr(plug, value)
            cmds.refresh(force=True)
        self.restored = True

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
