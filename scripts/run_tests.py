"""Run the RigFlow test suites.

Usage (from the repository root)::

    mayapy scripts/run_tests.py              # unit tests only (no Maya scene needed)
    mayapy scripts/run_tests.py --integration  # also run maya.standalone tests
    mayapy scripts/run_tests.py --only integration

The unit suite is pure Python; the integration suite initialises
``maya.standalone`` and therefore needs ``mayapy``.
"""

from __future__ import annotations

import argparse
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIT_DIR = os.path.join(ROOT, "tests", "unit")
INTEGRATION_DIR = os.path.join(ROOT, "tests", "integration")


def run_suite(start_dir: str, verbosity: int) -> bool:
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    if start_dir not in sys.path:
        sys.path.insert(0, start_dir)
    suite = unittest.defaultTestLoader.discover(start_dir, pattern="test_*.py", top_level_dir=start_dir)
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return result.wasSuccessful()


def run_integration(verbosity: int) -> bool:
    try:
        import maya.standalone
    except ImportError:
        print("Integration tests need mayapy (maya.standalone not importable).")
        return False
    maya.standalone.initialize(name="python")
    try:
        return run_suite(INTEGRATION_DIR, verbosity)
    finally:
        try:
            maya.standalone.uninitialize()
        except Exception:  # pragma: no cover - Maya quirks on shutdown
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--integration", action="store_true", help="also run Maya integration tests")
    parser.add_argument("--only", choices=("unit", "integration"), help="run a single suite")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)
    verbosity = 1 if args.quiet else 2

    ok = True
    if args.only != "integration":
        print("== Unit tests ==")
        ok = run_suite(UNIT_DIR, verbosity) and ok
    if args.integration or args.only == "integration":
        print("== Integration tests (maya.standalone) ==")
        ok = run_integration(verbosity) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
