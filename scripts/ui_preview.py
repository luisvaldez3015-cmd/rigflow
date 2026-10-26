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
    parser.add_argument("--screenshot", metavar="DIR", help="save offscreen workflow PNGs and exit")
    parser.add_argument("--width", type=int, default=1160)
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args(argv)
    if args.screenshot:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from rigflow.ui.qt import QtCore, QtWidgets, ensure_application_fonts
    from rigflow.ui.fake_controller import FakeController
    from rigflow.ui.main_window import MainWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    ensure_application_fonts()
    controller = FakeController()
    window = MainWindow(controller)
    window.resize(args.width, args.height)
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

    def capture_map(name):
        app.processEvents()
        for side, body in window.match_view.body_maps.items():
            path = output / (name + "_" + side + ".png")
            if not body.grab().save(str(path), "PNG"):
                raise RuntimeError("Could not save " + str(path))
            print(str(path))

    capture("01_setup_empty")
    controller.add_model_from_file("mixamorig_walk.fbx")
    capture("02_setup_one_model")
    destination = controller.add_model_from_selection()
    capture("03_setup_two_models")
    window.start_plan()
    clip = controller.session.active_clip
    # Show an intentional manual confirmation alongside automatic matches.
    match = clip.mapping.matches["Hips"]
    controller.set_manual_match(clip.clip_id, match.role, match.source, match.destination)
    capture("04_match")
    capture_map("04_match_body_map")
    view = window.match_view
    controller.selection = []
    view.click_slot("LeftHand", "destination")
    capture("04_match_selected")
    view.unmatch_button.click()
    view.click_slot("LeftHand", "source")
    capture("04_match_waiting")
    controller.selection = ["mixamorig:LeftHand"]
    view.poll_selection()
    controller.selection = ["l_wrist_JNT"]
    view.click_slot("LeftHand", "destination")
    normal_size = window.size()
    window.resize(960, 640)
    capture("04_match_min")
    view.map_tabs.setCurrentIndex(1)
    capture("04_match_hands_min")
    view.map_tabs.setCurrentIndex(0)
    window.resize(normal_size)
    from rigflow.skeleton.samples import build_skeleton, dense_spec
    old_skeleton, old_mapping = controller.session.rig.skeleton, clip.mapping
    dense = build_skeleton(dense_spec(), name="Dense humanoid")
    controller.session.rig.skeleton = destination.rig.skeleton = dense
    clip.mapping = None
    controller.auto_map(clip.clip_id)
    controller.selection = []
    view.click_slot("Spine4", "destination")
    capture("04_match_dense")
    window.resize(960, 640)
    capture("04_match_dense_min")
    controller.session.rig.skeleton = destination.rig.skeleton = old_skeleton
    clip.mapping = old_mapping
    view.set_clip(clip.clip_id)
    window.resize(normal_size)
    window.open_transfer(clip.clip_id)
    window.transfer_view._set_frame(24)
    capture("05_transfer")
    window.show_setup()
    source = controller.session.source
    controller.replace_model_from_file(source.character_id, "hero.ma")
    controller.replace_model_from_file(destination.character_id, "same_head.obj")
    capture("06_setup_similar_mesh")
    window.start_plan()
    capture("06_rig")
    window.rig_view.bind_button.click()
    clip = controller.session.active_clip
    window.open_match(clip.clip_id)
    view = window.match_view
    view.set_side("destination")
    view.clear_slot("LeftHand")
    controller.selection = []
    view.click_slot("LeftHand")
    capture("07_match_waiting")
    capture_map("07_match_waiting_map")
    controller.selection = ["l_wrist_JNT"]
    view.poll_selection()
    view.map_tabs.setCurrentIndex(1)
    capture("07_match_hands")
    capture_map("07_match_hands_map")
    window.show_setup()
    controller.replace_model_from_file(destination.character_id, "other.obj")
    capture("08_setup_dissimilar_mesh")
    window.close()
    window.deleteLater()
    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    return 0


if __name__ == "__main__":
    sys.exit(main())
