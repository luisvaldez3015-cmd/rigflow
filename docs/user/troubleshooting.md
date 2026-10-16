# Troubleshooting

Problems are grouped by the step where they appear. Every RigFlow error
message ends with a hint; this page expands on the most common ones. If a
problem is not listed, open an issue with the information in *Reporting a bug*.

## Installation and launch

**The shelf button does nothing / `ModuleNotFoundError: rigflow`.**
The module file points at a folder that moved or was deleted. Run
`scripts/install.py` again from the current location of the RigFlow folder.

**The window opens behind Maya or looks unstyled.**
Close it and run `import rigflow; rigflow.launch()` again. If it persists,
report your Maya version and whether the window is docked.

**Maya 2025/2026.** PySide6 support is implemented but not verified yet. If the
window fails to open, please attach the Script Editor output to an issue.

## Importing files

**"File imported but contained no joints or meshes".**
The file had only cameras, lights, curves or empty groups. Export the
skeleton (and optionally the mesh) again. For Mixamo, download *with skin* or
*without skin* — both work — but make sure an animation is actually included.

**The animation range is wrong or starts at frame 0.**
FBX files carry their own time range and frame rate. RigFlow reads the keys
that were imported; use Maya's time slider to confirm, and set the scene frame
rate before importing if it differs from the file's.

**Everything looks 100x too large or too small.**
A cm/m unit mismatch between the files. RigFlow warns when the height ratio
between source and destination is implausible. Set the scene linear unit to
match the destination before importing the source.

## Skeleton matching

**Many rows are yellow.**
The joints have no recognisable names (e.g. `joint12`) so only the hierarchy
analysis labeled them. Check a few key joints (hips, hands, feet) in the
viewport and confirm them; manual confirmations turn the rows green.

**Left and right are swapped.**
RigFlow guesses sides from the rest pose and corrects itself when the names
disagree. For a nameless skeleton facing -Z, link one side manually: the
mirrored joints follow once you link, for example, the left hand.

**A required role is red.**
The joint exists but its name was not recognised and the hierarchy was
unusual (extra joints between chest and clavicle, a pelvis node below the
hips...). Select the joint in the tree and link it to the role by hand.

**Fingers or toes are gray (unavailable).**
One of the two skeletons simply does not have them. They are skipped; the
transfer still works.

**A joint I expected to see is missing from the trees.**
Joints classified as helpers (twist/roll), end tips, facial joints, controls
or props are hidden from mapping on purpose. Hover the status strip to see the
list of ignored joints.

## Transfer

**"Required joint not mapped on the destination".**
Complete the red rows before previewing; the 15 required roles cannot be
skipped.

**The destination does not move during the preview.**
HumanIK could not retarget. Common causes: the source skeleton was not in a
rest pose when characterised (RigFlow puts it in the bind pose automatically,
but a skeleton with keyed joint orients or no bind pose may defeat this);
locked channels on the destination joints; constraints already driving them.
Unlock/remove them or bake onto an animation layer.

**My existing destination animation disappeared.**
Baking directly onto joints replaces their curves. Use the default *bake to
animation layer* option; the original animation is kept on the base layer
and can be restored by muting or deleting the RigFlow layer. Ctrl+Z right after
a transfer undoes it completely.

**The face stopped working after the transfer.**
RigFlow never writes to facial joints or controls. If a facial control is
parented under a body joint it still follows the body, which is expected. If
you believe a facial node was keyed by RigFlow, please report it with the
node name: that would be a bug.

## Reporting a bug

Open an issue on GitHub (Help → Report an Issue) and include:

- Maya version and OS (Help → About copies them for you).
- The exact steps and the full error text from the Script Editor.
- If possible, a small scene or the file that reproduces the problem.
