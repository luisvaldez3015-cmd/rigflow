"""Remove RigFlow from Maya.

Drag and drop into the viewport or run from the Script Editor. Deletes the
``rigflow.mod`` module file and every RigFlow shelf button. The checkout
itself is left untouched (delete the folder if you no longer want it).
Restart Maya to unload the package from the running session.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import install  # noqa: E402  (sibling installer module)


def uninstall(quiet: bool = False) -> dict:
    from maya import cmds

    module_path = os.path.join(install.modules_directory(), install.MODULE_NAME + ".mod")
    removed_module = False
    if os.path.isfile(module_path):
        os.remove(module_path)
        removed_module = True
    removed_buttons = 0 if cmds.about(batch=True) else install.remove_shelf_buttons()
    if removed_buttons:
        try:
            from maya import mel

            mel.eval("saveAllShelves $gShelfTopLevel;")
        except Exception:
            pass
    message = (
        "RigFlow uninstalled.\n\n"
        "Module file removed: {}\n"
        "Shelf buttons removed: {}\n\n"
        "Restart Maya to finish."
    ).format("yes" if removed_module else "not found", removed_buttons)
    print(message)
    if not quiet and not cmds.about(batch=True):
        cmds.confirmDialog(title="RigFlow uninstalled", message=message, button=["OK"])
    return {"module_file_removed": removed_module, "shelf_buttons_removed": removed_buttons}


def onMayaDroppedPythonFile(*_args, **_kwargs):  # noqa: N802
    uninstall()


if __name__ == "__main__":
    uninstall()
