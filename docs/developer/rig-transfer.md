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
Bounds use visible shapes only, excluding intermediate Orig shapes. The source
skinned mesh is sampled at rest; its bounds determine the fit, matching the
normalisation used for similarity and weight transfer. Low-level joints-only
fits fall back to joint bounds, but Setup requires source skin for rig transfer.
For destination bounds `Mmin`, `Mmax` and source bounds `Jmin`, `Jmax`:

```text
destination_height = Mmax[u] - Mmin[u]
source_height      = Jmax[u] - Jmin[u]
scale              = destination_height / source_height
```

Every copied joint's local translation, including the root's, is multiplied
by `scale`; its display radius is scaled too. Joint scale channels and
orientations are unchanged. Scale the source bounds, then:

```text
offset[u] = Mmin[u] - Jmin[u]
offset[i] = (Mmin[i] + Mmax[i] - Jmin[i] - Jmax[i]) / 2, for i != u
```

Moving the root by this world-space offset aligns the source and destination
mesh bottoms and bounding-box centres horizontally. Empty mesh selections,
already skinned geometry, and zero mesh or skeleton heights raise `SceneError`
with an actionable hint. The operation returns an unbound skeleton.

## Bind and UI workflow

Setup enables Transfer rig when a skinned source and mesh-only destination have
at least `config.MESH_SIMILARITY_THRESHOLD` (80%) rest-pose mesh similarity. The controller
calls fit, shows the destination meshes and copied joints, and lets the artist
move joints in Maya. **Bind** then calls `bind_skeleton(fit, meshes)`.
Each mesh gets a skinCluster using all fitted joints. Source weights are read at
rest with `MFnSkinCluster.getWeights`. Source and destination normalise along
Maya's up axis to unit height, with bottoms and horizontal bbox centres aligned.
Matching polygon connectivity copies weights directly by vertex index; different
topologies find the closest source surface and interpolate triangle weights
barycentrically. Influences map from `fit.source_joints` to `fit.joints`; weights
normalise and are written one row per vertex with `setAttr` (about 1 s for
20k vertices). The initial bind's `max_influences` parameter does not truncate
authored source weights. Plain `setAttr` calls are recorded by the bind undo
chunk, so Undo/Redo restore the copied weights without loading a plug-in (an
API write would need a custom command, and Maya's plug-in security would prompt
the artist to allow it).
The result records those skinClusters. A subsequent Match step reads the new
rest skeleton and maps the source animation before retargeting.

Fit, bind and removal each occupy one undo chunk. One undo immediately after
fit removes the entire copy. `remove_fit` deletes the copied joints and its
recorded skinClusters, preserves the meshes and source, and tolerates repeats.

Weight transfer on differing shapes is a starting point: polish by hand. Hats, hair and other tall geometry inflate the fitted height.
A uniform fit cannot adapt individual limb proportions; non-humanoids remain
untested. The workflow targets ordinary joint hierarchies rather than copying
the source's controls, constraints or rig implementation.

## Similarity

`scene.similarity.compare_meshes(source_meshes, destination_meshes, source_root=None)`
returns pure `core.similarity.MeshSimilarity` (percentage, verdict, differing
joint regions). It samples visible shapes at rest without recording scratch
pose changes on the undo queue. Matching connectivity uses corresponding
vertices; other meshes sample up to 2000 vertices per model and calculate a
symmetric closest-surface fraction within 3% height. Dominant source influences
identify regions well below the rest, preferring canonical roles such as Head.
The controller caches per character-id pair, invalidating when models/slots change.
External geometry edits require re-adding the affected model to refresh the score.
