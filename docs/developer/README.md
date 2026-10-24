# Developer Documentation

Start here if you want to understand, test or extend RigFlow.

| Document | Content |
|----------|---------|
| [architecture.md](architecture.md) | Layering rules and the contracts between modules (the agreement every contributor codes against). |
| [humanik-backend.md](humanik-backend.md) | The verified way to drive HumanIK from Python without its UI, including what silently fails. |
| [viewport-embedding.md](viewport-embedding.md) | How Maya model panels are embedded in the Qt views, and the pitfalls the in-Maya checks caught. |
| [../development/02-milestone-status.md](../development/02-milestone-status.md) | What is done, verified and pending, with measured numbers. |
| [../development/release-checklist.md](../development/release-checklist.md) | Steps for every tagged release. |
| [../development/01-feasibility-and-architecture.md](../development/01-feasibility-and-architecture.md) | Milestone 1 report: environment, MVP, risks. |
| [../../CONTRIBUTING.md](../../CONTRIBUTING.md) | Workflow, style, how to submit changes. |

## Repository layout

```
rigflow/            the package (see architecture.md for the layer rules)
tests/unit/         pure-Python tests, run anywhere in seconds
tests/integration/  maya.standalone tests, run with mayapy
scripts/            install.py, uninstall.py, run_tests.py, make_icons.py, ui_preview.py
docs/user/          artist-facing guides (linked from the Help menu)
docs/developer/     this folder
docs/development/   milestone reports and decisions
examples/           scripts that generate demo scenes procedurally
assets/             icon.svg, generated PNG icons and definition-map art
scripts/definition_art/  reproducible silhouette/layout generators and mockup renderer
```

## Running the tests

```bash
MAYAPY="C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe"
"$MAYAPY" -I scripts/run_tests.py                 # unit suite
"$MAYAPY" -I scripts/run_tests.py --integration   # unit + Maya integration
"$MAYAPY" -I scripts/run_tests.py --only integration
```

The `-I` flag isolates the interpreter from stray `PYTHONPATH` entries. Unit
tests must not import `maya`; integration tests get an initialised
`maya.standalone` from the runner and build their skeletons with
`tests/integration/scene_fixtures.py`, which reuses the pure specs in
`tests/unit/fixtures.py` so both suites describe the same characters.

## Working inside Maya

Install with `scripts/install.py` (it points Maya at your checkout), then
iterate with:

```python
import rigflow
rigflow.launch(dev_reload=True)   # reloads every rigflow module first
```

Set `RIGFLOW_LOG_LEVEL=DEBUG` in the environment for verbose logging in the
Script Editor.

## Adding support for a naming convention

1. Add keywords or two-token phrases to `rigflow/skeleton/naming.py`
   (`KEYWORDS`, `PHRASES`, `IGNORE_TOKENS`). Prefer adding to the vocabulary
   over adding special cases.
2. Add a fixture in `tests/unit/fixtures.py` and assertions in
   `tests/unit/test_naming.py` / `test_matcher.py`.
3. If the convention can be recognised as a whole, extend `detect_convention`.

## Adding a retargeting backend

Subclass `rigflow.retargeting.base.Retargeter`, implement `availability`,
`prepare`, `bake`, `cleanup`, register it in `rigflow/retargeting/__init__.py`
and add an integration test modelled on `tests/integration/test_retarget_*.py`.
Backends must only touch destination joints present in
`mapping.complete_pairs()` and must delete only nodes they created.
