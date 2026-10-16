<p align="center">
  <img src="assets/icon.svg" width="96" height="96" alt="RigFlow icon">
</p>

<h1 align="center">RigFlow — Animation Transfer for Maya</h1>

<p align="center">
  Transfer animation between characters with different proportions, skeletons and naming conventions.<br>
  <strong>Import → Match → Preview → Transfer → keep animating.</strong>
</p>

> **Status: alpha, under active development.** Skeleton analysis, joint
> matching, scene inspection, FBX/Maya import, the HumanIK and matrix
> retargeting backends and the PySide interface are implemented and covered by
> 73 unit tests and 44 Maya integration tests (Maya 2023 and 2024). Interactive
> verification inside Maya's UI is ongoing; no public release has been cut yet.
> See `CHANGELOG.md`.

## What RigFlow does

- Inspects a Maya scene and tells you what it found: meshes, joint hierarchies,
  skeleton roots, animation data.
- Labels both skeletons against a canonical humanoid template using joint
  names **and** hierarchy topology, with a confidence score for every joint.
- Shows the proposed source-to-destination joint matches with green / yellow /
  red statuses and lets you correct them by hand. Manual fixes survive recomputation.
- Retargets body animation onto the destination skeleton with a live preview
  before anything is baked (HumanIK where available, matrix-based fallback otherwise).
- Keeps the destination rig intact: facial, eye and jaw controls are never
  touched, so you can keep animating the face after the body transfer.

## What RigFlow does not do (yet)

- It does not retarget facial animation.
- It does not guarantee results on arbitrary non-humanoid or heavily
  customised rigs. Common humanoid skeletons come first.
- It does not bake onto animation controls of FK/IK rigs in v1; it bakes onto
  the destination skeleton joints (or an animation layer on them).

## Supported environment

| Maya | Python | Qt | Status |
|------|--------|----|--------|
| 2024 | 3.10 | PySide2 | Primary development target |
| 2023 | 3.9 | PySide2 | Tested headless (`mayapy`) |
| 2025 / 2026 | 3.11 | PySide6 | Planned through the Qt shim, not yet verified |

## Installation

1. Download or clone this repository to a permanent folder.
2. Start Maya and drag `scripts/install.py` into the viewport.
3. Click the new **RigFlow** shelf button.

The installer writes one Maya module file and one shelf button; nothing
else is modified. Uninstall with `scripts/uninstall.py`. Full details in
[`docs/user/installation.md`](docs/user/installation.md).

## Try it without assets

```python
import rigflow.scene.demo as demo
demo.build_demo_scene(new_scene=True)   # Mixamo-style source + short destination
import rigflow; rigflow.launch()
```

Select `root_JNT` → **Use selection** (Rig), then **From scene…** → `mixamorig:Hips`.

## Documentation

- [Installation](docs/user/installation.md) · [Compatibility](docs/user/compatibility.md)
- [Skeleton matching](docs/user/skeleton-matching.md) · [Animation transfer](docs/user/animation-transfer.md)
- [Troubleshooting](docs/user/troubleshooting.md)
- [Developer documentation](docs/developer/README.md) · [Architecture](docs/developer/architecture.md)

## Development

```bash
MAYAPY="C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe"
"$MAYAPY" -I scripts/run_tests.py                # unit tests (seconds)
"$MAYAPY" -I scripts/run_tests.py --integration  # + Maya integration tests
"$MAYAPY" scripts/ui_preview.py                  # open the UI with fake data, outside Maya
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`docs/development/01-feasibility-and-architecture.md`](docs/development/01-feasibility-and-architecture.md).

## License

MIT. See [`LICENSE`](LICENSE). RigFlow calls Autodesk Maya and HumanIK through
their public APIs and does not redistribute any Autodesk or third-party assets.
