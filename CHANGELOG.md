# Changelog

All notable changes to RigFlow are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Model-based Setup (owner's redesign): one **Add** per model (`.ma`, `.mb`,
  `.fbx`, `.obj` or the Maya selection); RigFlow detects the Mesh / Rig / Anim
  slots of each model, shows Model A and Model B side by side and proposes the
  process: transfer animation, transfer the rig first, or swap the direction
  when both models are animated (`rigflow.core.character`, `rigflow.core.plan`,
  `rigflow.scene.characters`).
- **Rig** step for mesh-only destinations: the source skeleton is copied at
  rest, fitted to the mesh height (visible shapes only) and position, shown in
  a viewport for adjustment, then bound with closest-distance weights
  (`rigflow.rigging`). Identical topology means Match is all green afterwards.
- Transferred animation is recorded on the destination model so it stays the
  destination; **New anim** replaces the source model. OBJ import. The in-Maya
  end-to-end check covers both scenarios (animation A → B, and mesh-only B:
  fit → bind → Match → Transfer).
- Project scaffold: package layout, licensing, contribution guidelines.
- Milestone 1 feasibility and architecture report (`docs/development/01-feasibility-and-architecture.md`).
- Pure-Python skeleton model (`rigflow.skeleton`): joint graph, naming-convention
  analysis and topology-based structural labeling of humanoid skeletons.
- Pure-Python joint mapping (`rigflow.mapping`): automatic matching with
  confidence scores, manual overrides, validation and JSON presets.
- Unit test suite runnable with `mayapy -m unittest` (no Maya scene required).
- Shared Maya helpers: undo chunks (`rigflow.scene.undo`) and a rest-pose
  context manager (`rigflow.scene.rest_pose`) verified in `maya.standalone`.
- Observable session state (`rigflow.core.session`) and the animation clip
  model (`rigflow.animation.clip`) that the UI and services share.
- Module-file based installer and uninstaller (`scripts/install.py`,
  `scripts/uninstall.py`), icon generator and shelf icons.
- Developer docs: architecture contracts and the verified HumanIK pipeline;
  user docs: installation, compatibility, skeleton matching, troubleshooting.
- Maya scene layer (`rigflow.scene`): inspection of meshes/skeletons/controls/
  animation, skeleton reading at current or rest pose, FBX/MA/MB import into
  private namespaces, unit and frame-rate queries, viewport panel helpers.
- PySide UI (`rigflow.ui`): main window with Model / Rig / Animation sections,
  matching workspace (hierarchy trees, mapping table with statuses, link
  overlay, presets), review view, Help menu, single-instance launcher, and an
  off-screen preview script with a fake controller.
- Canonical sample skeletons (`rigflow.skeleton.samples`) and an in-Maya demo
  scene builder (`rigflow.scene.demo`) with a skinned proxy mesh and a small
  facial setup that must stay untouched by transfers.
- Retargeting backends (`rigflow.retargeting`): HumanIK with live preview and
  a matrix-based fallback, baking onto an override animation layer (default)
  or directly, numeric verification of every bake (bone lengths, preview vs
  baked positions), cleanup of only the nodes RigFlow created, and closed undo
  steps per operation (preview, transfer, cancel).
- `Help → Create demo scene` builds the sample characters and loads them as
  destination in one click.
- Official brand: logo (wordmark with a Maya-joint "i"), transparent
  joint-glyph icons for the shelf and window, vector wordmark header, cyan
  accent colour.
- Step-based interface designed from the owner's sketches: **Setup** (Mesh /
  Rig / Anim slot cards, central add tile, Validate), **Match** (Mesh A / Mesh
  B viewports, Match / Unmatch / Auto-match driven by the live Maya joint
  selection, collapsible details table) and **Transfer** (preview viewport,
  playback, Transfer / New anim / Done).
- Embedded Maya viewports in the matching and review views are created under
  Qt layouts with private cameras and never touch the undo queue; an in-Maya
  end-to-end check (`scripts/maya_gui_check.py`) drives the real UI, bakes a
  transfer, verifies facial nodes stay untouched and that one Ctrl+Z removes it.
- Integration suite (`tests/integration`, 44 tests) covering scene inspection,
  FBX/MA round trips, rest pose, demo scene, both backends, layers and undo,
  passing on Maya 2023 and 2024.
