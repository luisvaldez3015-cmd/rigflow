# Rig transfer

`rigflow.rigging` gives a mesh-only model a copy of an existing skeleton.
It runs inside Maya; the character and transfer-plan models remain pure Python.
The public API exports `RigFitResult`, `fit_skeleton`, `bind_skeleton` and
`remove_fit`.

## Fit

`fit_skeleton(source_root, meshes, namespace=None, stance_time=None)` copies
the source hierarchy while `rigflow.scene.rest_pose.rest_pose` is active.
The context restores the source pose, animation connections and current time.
Only the copy is edited. Non-joint descendants are removed, input connections
are not duplicated, and any copied keys are cleared.

The copied root is parented to world. Joint names lose the source namespace
and enter the requested namespace, or the root namespace when none is given.
Maya makes colliding names unique. `RigFitResult` records the final joint names
in the same order as their source joints, plus the scale and root offset.
Joint orientations and rest rotations are retained for matching and HumanIK.

## Fit mathematics

Let `u` be the index of the scene up axis (`Y` or `Z`).
The mesh bounds come from `cmds.exactWorldBoundingBox(meshes)`.
The skeleton bounds enclose the copied joints' world-space positions.
For mesh bounds `Mmin`, `Mmax` and joint bounds `Jmin`, `Jmax`:

```text
mesh_height  = Mmax[u] - Mmin[u]
joint_height = Jmax[u] - Jmin[u]
scale        = mesh_height / joint_height
```

Every copied joint's local translation, including the root's, is multiplied
by `scale`; its display radius is scaled too. Joint scale channels and
orientations are unchanged. Recompute the joint bounds after scaling, then:

```text
offset[u] = Mmin[u] - Jmin[u]
offset[i] = (Mmin[i] + Mmax[i] - Jmin[i] - Jmax[i]) / 2, for i != u
```

Moving the root by this world-space offset grounds the lowest joint and
aligns the two bounding-box centres horizontally. Empty mesh selections,
already skinned geometry, and zero mesh or skeleton heights raise `SceneError`
with an actionable hint. The operation returns an unbound skeleton.

## Bind and UI workflow

Setup detects mesh-only destinations and proposes the Rig step. The controller
calls fit, shows the destination meshes and copied joints, and lets the artist
move joints in Maya. **Bind** then calls `bind_skeleton(fit, meshes)`.
Each mesh gets a closest-distance skinCluster using all fitted joints,
normalised weights, and four maximum influences by default.
The result records those skinClusters. A subsequent Match step reads the new
rest skeleton and maps the source animation before retargeting.

Fit, bind and removal each occupy one undo chunk. One undo immediately after
fit removes the entire copy. `remove_fit` deletes the copied joints and its
recorded skinClusters, preserves the meshes and source, and tolerates repeats.

Closest-distance binding is a starting point: artists should refine placement
and weights. Hats, hair and other tall geometry inflate the fitted height.
A uniform fit cannot adapt individual limb proportions; non-humanoids remain
untested. The workflow targets ordinary joint hierarchies rather than copying
the source's controls, constraints or rig implementation.
