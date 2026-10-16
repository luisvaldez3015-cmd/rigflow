# Embedding Maya model panels in the Qt interface

RigFlow shows live Maya viewports inside its own PySide windows (source and
destination previews in the matching workspace, the review viewport). This
page records what works and the mistakes the in-Maya checks caught, so nobody
has to rediscover them.

## The recipe that works (Maya 2024, PySide2)

```python
# Qt side (rigflow/ui/widgets/viewport_panel.py)
host = QtWidgets.QWidget()
host_layout = QtWidgets.QVBoxLayout(host)
host_layout.setObjectName("rigflowViewportLayout_<unique>")   # a QLayout name!

# Maya side (rigflow/scene/viewport.py), with undo suspended
cmds.setParent(host_layout.objectName())     # Maya resolves Qt LAYOUTS by name
pane = cmds.paneLayout()                     # becomes a child of host_layout
panel = cmds.modelPanel(menuBarVisible=False, camera=private_camera)
cmds.modelPanel(panel, edit=True, menuBarVisible=False)
cmds.modelEditor(panel, edit=True, displayAppearance="smoothShaded", hud=False, ...)
cmds.isolateSelect(panel, state=True); cmds.isolateSelect(panel, addSelected=True)
```

- `cmds.setParent` accepts the object name of a **QLayout**, not of a QWidget.
  Passing a widget name fails with `setParent: Object '...' not found`.
- Maya inserts the pane's native widget into that layout by itself. Wrapping
  the pane with `MQtUtil.findControl(pane) + wrapInstance` is only needed to
  keep a Python reference; a failed wrap must not tear the viewport down.
- Remember the `paneLayout` name returned at creation. Panels created under a
  Qt layout have no window path, so rebuilding the container from
  `modelPanel -q -parent` gives an unusable name.
- `cmds.viewFit(camera)` frames the current selection; there is no
  `selected` flag.
- Each panel gets a **private camera** duplicated from `persp` so framing one
  preview never moves the artist's camera; it is deleted with the panel.

## Keep UI furniture off the undo queue

Creating panels, duplicating/deleting preview cameras, selecting nodes to
frame them and deleting UI are *not* user edits. They run inside
`rigflow.scene.undo.suspended_undo()`. Otherwise Ctrl+Z after a transfer
would first undo a camera deletion instead of the bake, which is exactly what
the end-to-end check observed before the fix.

## Repainting

Embedded panels paint on Maya's idle loop. Automated screenshots must call
`cmds.refresh(force=True)` and process Qt events before grabbing pixels;
`frame_nodes` already refreshes after framing. `cmds.playblast(editorPanelName=panel,
offScreen=True, ...)` renders exactly what a given embedded panel shows and is
the reliable way to verify its content in `scripts/maya_gui_check.py`.

## Lifecycle

`ViewportPanel.release()` → `controller.delete_viewport(panel)` →
`scene.viewport.delete_model_panel(panel)` deletes the panel and its pane, then
the controller deletes the private camera. Views release their panels when
they are hidden (`MainWindow.show_main/open_review`) and on close, and the
controller's `shutdown()` covers anything left when the dock closes.
