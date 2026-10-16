"""mayapy scripts/ui_preview.py [--screenshot DIR] -- no Maya scene required."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", metavar="DIR", help="save four offscreen PNGs and exit")
    args = parser.parse_args(argv)
    if args.screenshot:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from rigflow.ui.qt import QtCore, QtWidgets
    from rigflow.ui.fake_controller import FakeController
    from rigflow.ui.main_window import MainWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    controller = FakeController()
    window = MainWindow(controller)
    window.show()
    app.processEvents()
    if not args.screenshot:
        return app.exec_() if hasattr(app, "exec_") else app.exec()
    output = Path(args.screenshot).resolve()
    try:
        output.relative_to(ROOT)
    except ValueError:
        pass
    else:
        parser.error("Screenshots must be written outside the repository.")
    output.mkdir(parents=True, exist_ok=True)

    def capture(name):
        # Settle layout requests and deferred viewport embedding before grabbing.
        for _ in range(3):
            app.processEvents()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        path = output / (name + ".png")
        if not window.grab().save(str(path), "PNG"):
            raise RuntimeError("Could not save " + str(path))
        print(str(path))

    capture("01_main_empty")
    controller.set_model_from_selection()
    controller.set_rig_from_selection()
    clip = controller.add_animation_from_file("Walk_Forward.fbx")
    controller.add_animation_from_file("Idle_Breathing.fbx")
    capture("02_main_populated")
    window.open_matching(clip.clip_id)
    # Show an intentional manual confirmation alongside automatic matches.
    match = clip.mapping.matches["Hips"]
    controller.set_manual_match(clip.clip_id, match.role, match.source, match.destination)
    capture("03_matching")
    window.open_review(clip.clip_id)
    capture("04_review")
    window.close()
    window.deleteLater()
    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    return 0


if __name__ == "__main__":
    sys.exit(main())
