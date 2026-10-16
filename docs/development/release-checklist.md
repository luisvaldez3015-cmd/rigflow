# Release checklist

Use this list for every tagged release. Nothing ships that is not verified.

## Before tagging

- [ ] `mayapy -I scripts/run_tests.py --integration` passes on every supported
      Maya version installed (currently 2023 and 2024).
- [ ] `scripts/maya_gui_check.py` passes inside interactive Maya (report `ok: true`,
      screenshots reviewed: viewports visible, statuses correct).
- [ ] `scripts/ui_preview.py --screenshot <dir>` renders the four reference
      screenshots; update `docs/images/` if the UI changed.
- [ ] `CHANGELOG.md`: move **Unreleased** entries under the new version and date.
- [ ] `rigflow/__init__.py`: bump `__version__`.
- [ ] `README.md` status paragraph and supported-version table are accurate.
- [ ] Documentation matches the implementation (no feature documented that is
      not tested).
- [ ] `git status` is clean; no temp files, local paths, or debug output.

## Package

The release ZIP contains only what the installer needs:

```
rigflow-<version>/
  rigflow/            (without __pycache__)
  scripts/install.py
  scripts/uninstall.py
  assets/icons/
  docs/
  README.md  LICENSE  CHANGELOG.md
```

Build it from a clean checkout:

```bash
git archive --format=zip --prefix=rigflow-<version>/ -o rigflow-<version>.zip v<version> \
  rigflow scripts/install.py scripts/uninstall.py assets/icons docs README.md LICENSE CHANGELOG.md
```

- [ ] Unzip the archive to a fresh folder on a machine (or user profile)
      without RigFlow, drag `scripts/install.py` into Maya, click the shelf
      button, run **Help → Create demo scene** and perform one transfer.
- [ ] Drag `scripts/uninstall.py`, restart Maya, confirm the button and module
      file are gone.

## Publish

- [ ] `git tag -a v<version> -m "RigFlow <version>"` and push the tag.
- [ ] Create the GitHub release, attach the ZIP, paste the changelog section.
- [ ] Update `config.REPO_URL` / documentation links if the repository moved.
- [ ] Announce (ArtStation / LinkedIn) only with recordings produced by this exact version.
