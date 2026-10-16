"""Build the distributable ZIP.

    mayapy scripts/build_release.py [--out DIR]

Packages only what an artist needs (package, installer, icons, docs, license)
into ``dist/<name>-<version>.zip`` with a top-level folder, skipping caches,
tests and development files. The archive unzips to a folder you can drop
``scripts/install.py`` from.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = "rigflow"
INCLUDE_DIRS = ("rigflow", "assets/icons", "docs/user", "examples")
INCLUDE_FILES = (
    "scripts/install.py", "scripts/uninstall.py", "README.md", "LICENSE", "CHANGELOG.md",
    "assets/icon.svg",
)
SKIP_DIR_NAMES = {"__pycache__", ".pytest_cache"}
SKIP_SUFFIXES = (".pyc", ".pyo", ".log")


def version() -> str:
    with io.open(os.path.join(ROOT, PACKAGE, "__init__.py"), "r", encoding="utf-8") as handle:
        match = re.search(r"__version__\s*=\s*[\"']([^\"']+)[\"']", handle.read())
    return match.group(1) if match else "0.0.0"


def iter_files():
    for relative in INCLUDE_FILES:
        path = os.path.join(ROOT, relative)
        if os.path.isfile(path):
            yield relative
    for directory in INCLUDE_DIRS:
        base = os.path.join(ROOT, directory)
        for folder, subdirs, files in os.walk(base):
            subdirs[:] = [d for d in subdirs if d not in SKIP_DIR_NAMES]
            for name in files:
                if name.endswith(SKIP_SUFFIXES):
                    continue
                full = os.path.join(folder, name)
                yield os.path.relpath(full, ROOT).replace("\\", "/")


def build(out_dir: str) -> str:
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    stem = "{}-{}".format(PACKAGE, version())
    archive = os.path.join(out_dir, stem + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        count = 0
        for relative in iter_files():
            bundle.write(os.path.join(ROOT, relative), "{}/{}".format(stem, relative))
            count += 1
    print("Wrote {} ({} files)".format(archive, count))
    return archive


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = parser.parse_args(argv)
    build(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
