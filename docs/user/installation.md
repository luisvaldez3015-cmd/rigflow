# Installation Guide

RigFlow installs like other professional Maya tools: through a **Maya module
file**. Nothing is copied into Maya's own folders and no preference file is
edited, so uninstalling is just as clean.

## Requirements

| Requirement | Notes |
|-------------|-------|
| Autodesk Maya 2023 or 2024 | Tested. Maya 2025/2026 (PySide6) is planned but not yet verified. |
| HumanIK plugins (`mayaHIK`, `mayaCharacterization`, `retargeterNodes`) | Ship with Maya; RigFlow loads them automatically. Without them the matrix-based fallback is used. |
| FBX plugin (`fbxmaya`) | Ships with Maya; needed to import `.fbx` animations. |

No Python packages need to be installed.

## Install

1. Download the latest release ZIP from the GitHub Releases page (or clone the
   repository) and unzip it somewhere permanent, for example
   `Documents/maya/tools/rigflow`. Do not unzip it inside a temporary folder:
   Maya loads the tool from this location every time it starts.
2. Start Maya.
3. Drag `scripts/install.py` from the unzipped folder into Maya's viewport.
4. A dialog confirms the installation and a **RigFlow** button appears on the
   current shelf.

If drag-and-drop is not available, open the Script Editor (Python tab) and run:

```python
exec(open(r"C:/path/to/rigflow/scripts/install.py").read())
```

### What the installer does

- Writes `rigflow.mod` into your Maya `modules` folder
  (`C:/Users/<you>/Documents/maya/modules` on Windows,
  `~/Library/Preferences/Autodesk/maya/modules` on macOS,
  `~/maya/modules` on Linux). The file points at the folder you unzipped.
- Adds a shelf button whose command is:

  ```python
  import rigflow
  rigflow.launch()
  ```

- Makes RigFlow importable in the current session so you can use it immediately.

## Launch

Click the **RigFlow** shelf button, or run `import rigflow; rigflow.launch()`
in the Script Editor. Clicking the button again raises the existing window; it
never opens duplicates.

## Update

Unzip the new version over the old folder (or `git pull`) and restart Maya.
If the folder moved, run `scripts/install.py` again to refresh the module file.

## Uninstall

Drag `scripts/uninstall.py` into the viewport (or run it from the Script
Editor). It deletes `rigflow.mod` and the shelf button. Restart Maya, then
delete the RigFlow folder if you no longer need it.

## Developer mode

When editing the source, reload every RigFlow module and reopen the window
without restarting Maya:

```python
import rigflow
rigflow.launch(dev_reload=True)
```

## Troubleshooting installation

- **"Run this installer inside Maya"** – the script was executed with plain
  Python or `mayapy`. Drop it into a running Maya session instead.
- **"RigFlow was registered but failed to import"** – the `rigflow` package
  folder is missing next to `scripts/`. Re-download the release ZIP.
- **No shelf button** – Maya was running in batch mode or the shelf could not
  be found. Create a Python shelf button manually with the launch command above.
- **Older Maya** – RigFlow needs Maya 2023+ (Python 3.9+). See
  `docs/user/compatibility.md`.
