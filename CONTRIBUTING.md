# Contributing to RigFlow

Thanks for your interest in RigFlow. This document explains how to set up a
development environment, run the tests and submit changes.

## Ground rules

- Be respectful and constructive. Bug reports with reproduction steps are gold.
- Keep Maya-dependent code inside `rigflow/scene`, `rigflow/retargeting`,
  `rigflow/animation` and `rigflow/ui`. Everything in `rigflow/skeleton`,
  `rigflow/mapping`, `rigflow/core` and `rigflow/utils` must import and run
  without Maya so it can be unit tested anywhere.
- Never document a feature as supported until it is implemented and tested.
- Do not commit proprietary assets (Mixamo downloads, studio rigs, etc.).
  Example scenes are generated procedurally by scripts in `examples/`.

## Supported environment

| Maya | Python | Qt binding |
|------|--------|------------|
| 2023 | 3.9    | PySide2 5.15 |
| 2024 | 3.10   | PySide2 5.15 |
| 2025 / 2026 | 3.11 | PySide6 (via `rigflow.ui.qt` shim, not yet verified on this machine) |

Write code that runs on Python 3.9+. Avoid syntax newer than 3.9
(no `match` statements, no `X | Y` unions at runtime).

## Running the tests

RigFlow uses the standard library `unittest` so no extra dependency is needed.

```bash
# Pure-Python tests (fast, no Maya session):
"C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe" -m unittest discover -s tests/unit -v

# Maya integration tests (initialises maya.standalone, slower):
"C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe" scripts/run_tests.py --integration
```

On macOS/Linux replace the path with your `mayapy` binary.

## Code style

- Follow PEP 8 with a 100-character line limit.
- Use type hints and docstrings for public functions and classes.
- Prefer small, focused modules. Avoid duplicating logic across modules.
- Log through `rigflow.core.logging.get_logger(__name__)`; do not `print`.
- Raise `rigflow.core.errors.RigFlowError` subclasses with actionable messages.

## Submitting changes

1. Fork the repository and create a feature branch.
2. Add or update unit tests for behaviour you change.
3. Run the unit tests and, if you touched Maya code, the integration tests.
4. Update `CHANGELOG.md` under **Unreleased**.
5. Open a pull request describing the motivation, the approach and how you
   tested it. Screenshots or short recordings are welcome for UI changes.

## Reporting bugs

Open a GitHub issue and include: Maya version, OS, RigFlow version, the exact
steps to reproduce, the full error text from the Script Editor and, when
possible, a small scene or a script that rebuilds the problem.
