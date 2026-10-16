# Milestone status

_Last updated 2026-10-16._ Honest snapshot of what is done, verified and pending.
"Verified" means covered by an automated test or by the in-Maya end-to-end
check (`scripts/maya_gui_check.py`), not merely "the UI exists".

| Milestone | Status | Evidence |
|-----------|--------|----------|
| M1 Feasibility and architecture | Done | `01-feasibility-and-architecture.md`, `docs/developer/humanik-backend.md` (HIK spike on Maya 2023/2024). |
| M2 Working interface | Done; drag-and-drop of files still to be tried by hand | 10 off-screen UI smoke tests; `scripts/ui_preview.py` screenshots; in-Maya check drives the real dockable window through all three views with embedded, undo-neutral viewports (content verified by playblast). |
| M3 Skeleton detection and matching | Done | 63 pure unit tests (naming, topology, fusion, overrides, validation, presets); integration tests on scene-built skeletons and FBX/MA round trips. |
| M4 Animation transfer | Done for humanoid skeletons | 20 retargeting integration tests (HIK live preview, bake direct/layer, layer preservation, partial mappings, undo, matrix fallback); in-Maya check: 20 roles baked, bone-length error 2e-14 cm, facial setup untouched, one-step undo/redo. |
| M5 Reliability | In progress | Invalid files, missing roles, ambiguous names, nameless skeletons, unit mismatch and excluded roles are tested. Pending: real Mixamo/MetaHuman files from disk, control-rig destinations, Maya 2025/2026 (PySide6). |
| M6 Documentation and release | In progress | User guides (installation, user guide, compatibility, matching, transfer, troubleshooting) and developer docs exist. Pending: GitHub repository, release ZIP, screenshots in docs, GitHub Pages decision. |
| M7 Portfolio | Not started | Needs real screen recordings once M5 is closed. |

## Verified numbers (Maya 2024, demo scene, 48 frames)

| Metric | Value |
|--------|-------|
| Unit tests | 73 passing (also on Maya 2023) |
| Integration tests | 44 passing (also on Maya 2023) |
| Required roles auto-matched green (Mixamo → custom) | 15 / 15 (20 roles total incl. spine chain, neck, toes) |
| HIK characterise + bake, 20 joints | ≈ 1 s headless, ≈ 3 s with verification inside the UI |
| Destination hips rise vs source rise | 0.667 (= hip-height ratio 66 / 100) |
| Max bone-length change after bake | 1.8e-14 cm |
| Preview vs baked position difference | 0.0 cm |
| Facial joints / jaw control keys written | 0 |

## Known gaps to close before a public release

1. Documentation screenshots: `QScreen.grabWindow` does not composite Maya's
   OpenGL panels, so the automated captures show the Qt chrome only; the
   embedded viewports themselves are verified through per-panel playblasts
   (`*_playblast_*.png` in the check output). Real screenshots for the README
   must be taken by hand or assembled from playblasts.
2. A stance-frame picker for clips that do not start in a grounded pose.
3. Real-world asset pass: Mixamo FBX with skin, MetaHuman body, AdvancedSkeleton rig.
4. Maya 2025/2026 verification (PySide6 shim untested on a real install).
5. Release packaging (ZIP with `rigflow/`, `scripts/`, `assets/`, docs) and the
   public GitHub repository.
