"""RigFlow installer for Autodesk Maya.

Two ways to use it:

1. **Drag and drop** this file into Maya's viewport. Maya runs it and the
   installer registers RigFlow and adds a shelf button.
2. Or run it from the Script Editor (Python tab)::

       exec(open(r"C:/path/to/rigflow/scripts/install.py").read())

What it does (and nothing else):

* Writes ``rigflow.mod`` into your Maya ``modules`` folder
  (``Documents/maya/modules`` on Windows). The module file points at this
  checkout, so Maya adds the package to ``sys.path`` on every start.
* Makes the package importable in the current session right away.
* Adds a **RigFlow** button to the current shelf (or to a shelf named
  ``RigFlow`` when the current shelf cannot be determined).

It never edits ``userSetup.py``, ``Maya.env`` or any other preference.
To remove RigFlow run ``scripts/uninstall.py`` (or delete ``rigflow.mod`` and
the shelf button by hand).
"""

from __future__ import annotations

import io
import os
import re
import sys

MODULE_NAME = "rigflow"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ICON_RELATIVE = os.path.join("assets", "icons", "rigflow_shelf.png")
SHELF_LABEL = "RigFlow"
SHELF_COMMAND = "import rigflow\nrigflow.launch()"
MIN_MAYA_VERSION = 2023


def _package_version() -> str:
    init_path = os.path.join(ROOT, MODULE_NAME, "__init__.py")
    try:
        with io.open(init_path, "r", encoding="utf-8") as handle:
            match = re.search(r"__version__\s*=\s*[\"']([^\"']+)[\"']", handle.read())
            if match:
                return match.group(1)
    except (IOError, OSError):
        pass
    return "0.0.0"


def _in_maya() -> bool:
    try:
        from maya import cmds

        cmds.about(version=True)
        return True
    except Exception:
        return False


def module_file_contents(root: str, version: str) -> str:
    root = root.replace("\\", "/")
    return (
        "+ {name} {version} {root}\n"
        "PYTHONPATH +:= \n"
        "icons: assets/icons\n"
    ).format(name=MODULE_NAME, version=version, root=root)


def modules_directory() -> str:
    from maya import cmds

    directory = os.path.join(cmds.internalVar(userAppDir=True), "modules")
    if not os.path.isdir(directory):
        os.makedirs(directory)
    return directory


def write_module_file() -> str:
    path = os.path.join(modules_directory(), MODULE_NAME + ".mod")
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(module_file_contents(ROOT, _package_version()))
    return path


def register_now() -> None:
    """Make ``import rigflow`` work in this session without restarting Maya."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    icons = os.path.join(ROOT, "assets", "icons")
    xbm = os.environ.get("XBMLANGPATH", "")
    if icons not in xbm:
        os.environ["XBMLANGPATH"] = (xbm + os.pathsep + icons) if xbm else icons
    try:
        from maya import cmds

        cmds.loadModule(scan=True)
        cmds.loadModule(load=MODULE_NAME)
    except Exception:
        pass  # Not critical: sys.path is set and the .mod is read on next start.


def _current_shelf():
    from maya import cmds, mel

    try:
        top = mel.eval("$tmp = $gShelfTopLevel")
        if top and cmds.tabLayout(top, exists=True):
            return cmds.tabLayout(top, q=True, selectTab=True)
    except Exception:
        pass
    return None


def remove_shelf_buttons() -> int:
    """Delete every RigFlow shelf button (all shelves). Returns the count."""
    from maya import cmds, mel

    removed = 0
    try:
        top = mel.eval("$tmp = $gShelfTopLevel")
        shelves = cmds.tabLayout(top, q=True, childArray=True) or []
    except Exception:
        return 0
    for shelf in shelves:
        for button in cmds.shelfLayout(shelf, q=True, childArray=True) or []:
            try:
                if cmds.shelfButton(button, q=True, label=True) == SHELF_LABEL:
                    cmds.deleteUI(button)
                    removed += 1
            except Exception:
                continue
    return removed


def create_shelf_button() -> str:
    from maya import cmds, mel

    remove_shelf_buttons()
    shelf = _current_shelf()
    if shelf is None:
        top = mel.eval("$tmp = $gShelfTopLevel")
        shelf = cmds.shelfLayout(SHELF_LABEL, parent=top)
    icon = os.path.join(ROOT, ICON_RELATIVE)
    if not os.path.isfile(icon):
        icon = "commandButton.png"
    button = cmds.shelfButton(
        parent=shelf,
        label=SHELF_LABEL,
        annotation="RigFlow — Animation Transfer for Maya",
        image=icon,
        image1=icon,
        command=SHELF_COMMAND,
        sourceType="python",
        style="iconOnly",
    )
    try:
        mel.eval("saveAllShelves $gShelfTopLevel;")
    except Exception:
        pass
    return button


def install(create_shelf: bool = True, quiet: bool = False) -> dict:
    if not _in_maya():
        raise RuntimeError(
            "Run this installer inside Maya: drag scripts/install.py into the viewport "
            "or execute it from the Script Editor."
        )
    from maya import cmds

    version = int(str(cmds.about(version=True)).split(".")[0].split()[0])
    if version < MIN_MAYA_VERSION:
        raise RuntimeError(
            "RigFlow needs Maya {} or newer (found {}).".format(MIN_MAYA_VERSION, version)
        )
    if not os.path.isdir(os.path.join(ROOT, MODULE_NAME)):
        raise RuntimeError("Package folder not found next to scripts/: {}".format(ROOT))

    module_path = write_module_file()
    register_now()
    try:
        import importlib

        importlib.import_module(MODULE_NAME)
    except Exception as exc:
        raise RuntimeError("RigFlow was registered but failed to import: {}".format(exc))

    shelf_button = None
    if create_shelf and not cmds.about(batch=True):
        shelf_button = create_shelf_button()

    summary = {
        "module_file": module_path,
        "package_root": ROOT,
        "shelf_button": shelf_button,
        "version": _package_version(),
    }
    message = (
        "RigFlow {version} installed.\n\n"
        "Module file: {module_file}\n"
        "Package: {package_root}\n"
        "{shelf}"
    ).format(
        shelf="A RigFlow button was added to your shelf." if shelf_button else "",
        **summary
    )
    print(message)
    if not quiet and not cmds.about(batch=True):
        cmds.confirmDialog(title="RigFlow installed", message=message, button=["OK"])
    return summary


def onMayaDroppedPythonFile(*_args, **_kwargs):  # noqa: N802 (Maya callback name)
    """Entry point Maya calls when the file is dropped into the viewport."""
    install()


if __name__ == "__main__":
    install()
