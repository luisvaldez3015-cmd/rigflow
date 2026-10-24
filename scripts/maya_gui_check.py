"""End-to-end check of RigFlow inside an interactive Maya session.

Launch Maya with this script, for example from a shell::

    "C:/Program Files/Autodesk/Maya2024/bin/maya.exe" -command \
      "python(\"exec(open('C:/path/to/rigflow/scripts/maya_gui_check.py').read())\")"

The script builds the demo scene, opens the real RigFlow window (real
controller, main viewport definitions and Rig/Transfer embedded viewports),
walks the whole workflow — add models, define slots in both selection orders,
verify isolation/X-ray/restoration, live preview, review, bake — and
captures a screenshot at each step. It then verifies on the real scene that:

* the destination joints received keys on the RigFlow animation layer,
* the facial joints and the jaw control received no keys at all,
* the jaw control still drives the jaw after the transfer,
* the source animation is unchanged.

Results are written to ``%TEMP%/rigflow_gui_check/report.json`` together with
the PNGs. Maya quits at the end unless ``RIGFLOW_GUI_KEEP_OPEN=1`` is set.
Nothing is written inside the repository and no preferences are modified
(the package is added to ``sys.path`` for this session only).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in globals() else None
if ROOT is None:  # executed through exec(): locate the repo from this file's known layout
    for candidate in sys.argv + [os.getcwd()]:
        if os.path.isdir(os.path.join(candidate, "rigflow")):
            ROOT = candidate
            break
if ROOT is None:
    ROOT = os.environ.get("RIGFLOW_ROOT", "")
if ROOT and ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_DIR = os.environ.get("RIGFLOW_GUI_OUTPUT", os.path.join(tempfile.gettempdir(), "rigflow_gui_check"))
if not os.path.isdir(OUT_DIR):
    os.makedirs(OUT_DIR)

REPORT = {"steps": [], "checks": {}, "errors": [], "root": ROOT}


def _log(step, **data):
    entry = {"step": step, "time": round(time.time(), 2)}
    entry.update(data)
    REPORT["steps"].append(entry)
    print("[rigflow-gui-check] {} {}".format(step, data if data else ""))


def _grab(window, name):
    from maya import cmds
    from rigflow.ui.qt import QtCore, QtGui, QtWidgets
    from rigflow.ui.widgets.viewport_panel import ViewportPanel

    # Let embedded model panels paint before capturing the screen pixels.
    _pump(0.5)
    cmds.refresh(force=True)
    _pump(0.5)
    QtWidgets.QApplication.processEvents()
    path = os.path.join(OUT_DIR, name + ".png")
    # Widget capture cannot contain an unrelated application if Windows denies
    # focus to a background check. Native OpenGL children are captured directly
    # from their real Maya panel and composited into their actual Qt rectangle.
    pixmap = window.grab()
    for index, vp in enumerate(window.findChildren(ViewportPanel)):
        if vp.isVisible() and vp.panel:
            shot = os.path.join(OUT_DIR, "{}_viewport_{}.png".format(name, index))
            cmds.playblast(editorPanelName=vp.panel, frame=[cmds.currentTime(q=True)],
                           format="image", compression="png", completeFilename=shot,
                           viewer=False, showOrnaments=False, percent=100,
                           widthHeight=[max(64, vp.host.width()), max(64, vp.host.height())],
                           offScreen=True, forceOverwrite=True)
            painter = QtGui.QPainter(pixmap)
            origin = vp.host.mapTo(window, QtCore.QPoint(0, 0))
            painter.drawPixmap(QtCore.QRect(origin, vp.host.size()), QtGui.QPixmap(shot))
            painter.end()
    REPORT["capture_method"] = "Qt widget grab with live Maya viewport playblasts in their Qt rectangles"
    pixmap.save(path, "PNG")
    _log("screenshot", file=path, size=[pixmap.width(), pixmap.height()])
    return path


def _viewport_diagnostics(window, tag):
    """Record what every ViewportPanel in the window is doing, plus a playblast of it."""
    from maya import cmds
    from rigflow.ui.widgets.viewport_panel import ViewportPanel

    entries = []
    for index, vp in enumerate(window.findChildren(ViewportPanel)):
        entry = {
            "title": vp.header.text(), "visible": vp.isVisible(), "panel": vp.panel,
            "attempted": vp._attempted, "placeholder_visible": vp.placeholder.isVisible(),
            "isolate": list(vp.isolate), "size": [vp.host.width(), vp.host.height()],
            "host_layout": [
                {"name": vp.host_layout.itemAt(i).widget().objectName(),
                 "visible": vp.host_layout.itemAt(i).widget().isVisible(),
                 "size": [vp.host_layout.itemAt(i).widget().width(), vp.host_layout.itemAt(i).widget().height()]}
                for i in range(vp.host_layout.count()) if vp.host_layout.itemAt(i).widget()],
        }
        if vp.panel and cmds.modelPanel(vp.panel, exists=True):
            camera = cmds.modelPanel(vp.panel, q=True, camera=True)
            entry["camera"] = camera
            entry["camera_position"] = [round(v, 2) for v in cmds.xform(camera, q=True, ws=True, t=True)]
            entry["isolate_state"] = cmds.isolateSelect(vp.panel, q=True, state=True)
            try:
                entry["isolate_set"] = cmds.isolateSelect(vp.panel, q=True, viewObjects=True)
            except Exception as exc:
                entry["isolate_set"] = str(exc)
            shot = os.path.join(OUT_DIR, "{}_playblast_{}.png".format(tag, index))
            try:
                cmds.playblast(editorPanelName=vp.panel, frame=[cmds.currentTime(q=True)],
                               format="image", compression="png", completeFilename=shot,
                               viewer=False, showOrnaments=False, percent=100,
                               widthHeight=[640, 360], offScreen=True, forceOverwrite=True)
                entry["playblast"] = shot
            except Exception as exc:
                entry["playblast_error"] = str(exc)
        entries.append(entry)
    REPORT.setdefault("viewports", {})[tag] = entries
    REPORT["checks"][tag + "_viewports_embedded"] = all(e["panel"] for e in entries if e["visible"])
    REPORT["checks"][tag + "_hidden_viewports_released"] = all(not e["panel"] for e in entries if not e["visible"])
    _log("viewports", tag=tag, count=len(entries))


def _pump(seconds=0.5):
    from rigflow.ui.qt import QtCore, QtWidgets

    end = time.time() + seconds
    while time.time() < end:
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
        time.sleep(0.02)


def run():
    from maya import cmds
    REPORT["maya_version"] = cmds.about(version=True)

    import rigflow
    from rigflow.scene.demo import build_demo_scene

    cmds.file(new=True, force=True)
    demo = build_demo_scene()
    _log("demo_scene", source=demo.source_root, destination=demo.destination_root, mesh=demo.destination_mesh)

    window = rigflow.launch()
    controller = window.controller
    import logging
    class ServiceErrors(logging.Handler):
        def emit(self, record):
            REPORT.setdefault("service_errors", []).append(self.format(record))
    service_errors = ServiceErrors(level=logging.ERROR)
    logging.getLogger("rigflow.ui.controller").addHandler(service_errors)
    REPORT["status_log"] = []
    controller.session.subscribe(
        lambda event, payload: REPORT["status_log"].append(payload)
        if getattr(event, "value", event) == "status" else None)
    _pump(1.0)
    _grab(window, "01_main_empty")

    cmds.select(demo.source_root)
    model_a = controller.add_model_from_selection()
    REPORT["checks"]["model_a_detected"] = bool(
        model_a and model_a.has_rig and model_a.has_anim and not model_a.has_mesh)
    _grab(window, "02_setup_one_model")
    cmds.select(demo.destination_mesh)
    model_b = controller.add_model_from_selection()
    REPORT["checks"]["model_b_detected"] = bool(model_b and model_b.has_mesh and model_b.has_rig)
    REPORT["checks"]["animation_plan"] = controller.session.plan.kind == "animation"
    REPORT["checks"]["animation_source_a"] = bool(model_a and controller.session.source is model_a)
    _grab(window, "03_setup_plan")
    from rigflow.scene.viewport import main_model_panel
    original_panel = main_model_panel()
    cmds.modelEditor(original_panel, edit=True, joints=False, polymeshes=True, jointXray=False)
    cmds.select(demo.destination_mesh, replace=True)
    cmds.isolateSelect(original_panel, state=True)
    cmds.isolateSelect(original_panel, addSelected=True)
    window.start_plan()
    REPORT["checks"]["start_opens_match"] = window.stack.currentWidget() is window.match_view
    _pump(0.3)
    REPORT["checks"]["rig_valid"] = bool(controller.session.rig and controller.session.rig.valid)
    REPORT["checks"]["model_valid"] = bool(controller.session.model and controller.session.model.valid)
    clip = controller.session.active_clip
    REPORT["checks"]["clip_added"] = clip is not None
    if clip is None:
        raise RuntimeError("Clip was not added")
    report = window.validate_active()
    REPORT["checks"]["mapping_ok"] = report.ok
    REPORT["checks"]["mapping_summary"] = clip.mapping.summary() if clip.mapping else {}
    _pump(1.0)
    from PySide2.QtTest import QTest
    from rigflow.ui.qt import QtCore
    from rigflow.scene.viewport import DefinitionViewport
    view = window.match_view
    lease = controller._definition_viewport
    if lease is None:
        raise RuntimeError("Match did not capture the main viewport")
    main_panel = lease.panel
    baseline = lease
    def restored_to(snapshot):
        now = DefinitionViewport.capture(main_panel)
        return (now.isolated == snapshot.isolated and sorted(now.members) == sorted(snapshot.members)
                and now.flags == snapshot.flags and now.camera_values == snapshot.camera_values
                and all(abs(a-b) < 1e-7 for a, b in zip(now.matrix, snapshot.matrix)))
    def click(role):
        QTest.mouseClick(view.body_map, QtCore.Qt.LeftButton, pos=view.body_map.slot_position(role))
        _pump(.2)
    def main_shot(name):
        shot = os.path.join(OUT_DIR, name + ".png")
        cmds.playblast(editorPanelName=main_panel, frame=[cmds.currentTime(q=True)], format="image",
                       compression="png", completeFilename=shot, viewer=False, showOrnaments=False,
                       percent=100, widthHeight=[960, 640], offScreen=True, forceOverwrite=True)
        return shot
    REPORT["checks"]["match_main_isolated"] = bool(cmds.isolateSelect(main_panel, q=True, state=True))
    REPORT["checks"]["match_joint_xray"] = bool(cmds.modelEditor(main_panel, q=True, jointXray=True))
    REPORT["checks"]["match_no_embedded_panels"] = not view.findChildren(__import__(
        "rigflow.ui.widgets.viewport_panel", fromlist=["ViewportPanel"]).ViewportPanel)
    hand = clip.mapping.matches["LeftHand"]
    source_hand, destination_hand = hand.source, hand.destination
    view.clear_slot("LeftHand")
    cmds.select(clear=True)
    click("LeftHand")
    REPORT["checks"]["slot_first_waits"] = view.waiting == "LeftHand"
    _grab(window, "04_match_waiting")
    cmds.select(destination_hand, replace=True)
    _pump(.3)
    REPORT["checks"]["wrong_model_rejected"] = view.waiting == "LeftHand" and hand.source is None
    cmds.select(source_hand, replace=True)
    _pump(.3)
    REPORT["checks"]["slot_first_assigned"] = hand.source == source_hand and view.waiting is None
    view.model_buttons["destination"].click()
    _pump(.3)
    members = cmds.sets(cmds.isolateSelect(main_panel, q=True, viewObjects=True), q=True) or []
    REPORT["checks"]["switch_isolates_b"] = any(destination_hand.rsplit("|", 1)[-1] == n.rsplit("|", 1)[-1] for n in members) and not any(source_hand.rsplit("|", 1)[-1] == n.rsplit("|", 1)[-1] for n in members)
    view.clear_slot("LeftHand")
    cmds.select(destination_hand, replace=True)
    click("LeftHand")
    REPORT["checks"]["joint_first_assigned"] = hand.destination == destination_hand
    cmds.select(clear=True)
    click("LeftHand")
    REPORT["checks"]["assigned_slot_selects_scene"] = controller.definition_joint(clip.clip_id, "destination", (cmds.ls(sl=True, long=True) or [""])[0]) == destination_hand
    for display in ("Bones", "Mesh", "Both"):
        view.display_buttons[display].click()
        REPORT["checks"]["display_" + display.lower()] = (
            bool(cmds.modelEditor(main_panel, q=True, joints=True)) == (display != "Mesh") and
            bool(cmds.modelEditor(main_panel, q=True, polymeshes=True)) == (display != "Bones"))
    REPORT["main_match_viewport"] = main_shot("04_main_viewport_both")
    view.display_buttons["Bones"].click()
    REPORT["main_bones_viewport"] = main_shot("04_main_viewport_bones")
    view.display_buttons["Both"].click()
    view.map_tabs.setCurrentIndex(1)
    _grab(window, "04_match_hands")
    view.map_tabs.setCurrentIndex(0)
    REPORT["checks"]["manual_match"] = bool(clip.mapping.matches["LeftHand"].manual)
    _grab(window, "04_matching")
    normal_size = window.size()
    # Maya owns the floating workspace's layout and overrides child resize().
    # Resize its host by the content delta to exercise the real minimum size.
    host = window.window()
    host.resize(host.width() + 960 - window.width(), host.height() + 640 - window.height())
    _pump(.3)
    REPORT["checks"]["match_minimum_size"] = (window.width(), window.height()) == (960, 640)
    _grab(window, "04_matching_min")
    view.map_tabs.setCurrentIndex(1)
    _grab(window, "04_match_hands_min")
    view.map_tabs.setCurrentIndex(0)
    host.resize(host.width() + normal_size.width() - window.width(),
                host.height() + normal_size.height() - window.height())
    _viewport_diagnostics(window, "matching")
    window.show_setup()
    REPORT["checks"]["back_restores_main_viewport"] = restored_to(baseline)
    cmds.isolateSelect(main_panel, state=False)
    cmds.modelEditor(main_panel, edit=True, joints=True, polymeshes=False, jointXray=True)
    baseline = DefinitionViewport.capture(main_panel)
    window.open_match(clip.clip_id)
    window.show_setup()
    REPORT["checks"]["disabled_isolate_restored"] = restored_to(baseline)
    window.open_match(clip.clip_id)

    # Keys before the transfer, to prove facial nodes stay untouched.
    facial_nodes = list(demo.facial_joints) + list(demo.facial_controls)
    def key_counts(nodes):
        return {n: int(cmds.keyframe(n, q=True, keyframeCount=True) or 0) for n in nodes}
    facial_before = key_counts(facial_nodes)
    source_before = key_counts(list(demo.source_joints.values()))

    window.open_transfer(clip.clip_id)
    REPORT["checks"]["transfer_restores_main_viewport"] = restored_to(baseline)
    REPORT["checks"]["preview_started"] = bool(window.transfer_view._preview_ready)
    controller.set_frame(24)
    _pump(1.0)
    hips_preview = cmds.xform(demo.destination_joints["pelvis_JNT"], q=True, ws=True, t=True)
    REPORT["checks"]["preview_hips_y_frame24"] = round(hips_preview[1], 3)
    _pump(1.0)
    controller.set_frame(24)
    _grab(window, "05_review_preview_f24")
    _viewport_diagnostics(window, "review")

    result = controller.bake(clip.clip_id, to_layer=True)
    REPORT["checks"]["bake_result"] = None if result is None else {
        "backend": result.backend, "layer": result.layer, "baked_joints": len(result.baked_joints),
        "verification": result.verification, "warnings": result.warnings,
    }
    window.show_setup()
    _pump(0.5)
    _grab(window, "06_main_transferred")

    # Undo must be checked before any other undoable command runs.
    layers = cmds.ls(type="animLayer")
    REPORT["checks"]["anim_layers"] = layers
    cmds.undo()
    REPORT["checks"]["undo_removed_layer"] = not [
        l for l in cmds.ls(type="animLayer") if "rigflow" in l.lower()]
    cmds.redo()
    REPORT["checks"]["redo_restored_layer"] = bool(
        [l for l in cmds.ls(type="animLayer") if "rigflow" in l.lower()])
    pelvis_keys = int(cmds.keyframe(demo.destination_joints["pelvis_JNT"], q=True, keyframeCount=True) or 0)
    REPORT["checks"]["pelvis_key_count"] = pelvis_keys
    facial_after = key_counts(facial_nodes)
    REPORT["checks"]["facial_untouched"] = facial_after == facial_before
    REPORT["checks"]["facial_keys"] = facial_after
    REPORT["checks"]["source_untouched"] = key_counts(list(demo.source_joints.values())) == source_before

    # The jaw control must still drive the jaw.
    control = demo.facial_controls[0]
    jaw = demo.facial_joints[0]
    before = cmds.getAttr(jaw + ".rotate")[0]
    cmds.setAttr(control + ".rotateX", 25.0)
    after = cmds.getAttr(jaw + ".rotate")[0]
    cmds.setAttr(control + ".rotateX", 0.0)
    REPORT["checks"]["jaw_control_drives_jaw"] = any(abs(a - b) > 1.0 for a, b in zip(before, after))

    cmds.currentTime(24)
    hips_baked = cmds.xform(demo.destination_joints["pelvis_JNT"], q=True, ws=True, t=True)
    REPORT["checks"]["baked_hips_y_frame24"] = round(hips_baked[1], 3)
    REPORT["checks"]["hips_moved_up"] = hips_baked[1] > 66.0 + 10.0

    # A fresh scenario has an authored, skinned source and a similar mesh-only B.
    window.show_setup()
    removed = controller.remove_model(model_b.character_id)
    REPORT["checks"]["model_b_removed"] = removed is model_b
    controller.remove_model(model_a.character_id)
    cmds.file(new=True, force=True)
    demo = build_demo_scene(animate=False, with_face=False)
    from rigflow.scene.demo import animate_jump
    from rigflow.skeleton.samples import custom_roles
    copy = cmds.duplicate(demo.destination_mesh)[0]
    for channel in ("translateX", "translateY", "translateZ", "scaleX", "scaleY", "scaleZ"):
        cmds.setAttr(copy + "." + channel, lock=False)
    cmds.setAttr(copy + ".scale", .8, .8, .8)
    cmds.move(200, 0, 0, copy, relative=True, worldSpace=True)
    animate_jump(demo.destination_joints, custom_roles())
    cmds.select(demo.destination_mesh, replace=True)
    model_a = controller.add_model_from_selection()
    # Dissimilar geometry must keep both cards visible and disable rig transfer.
    sphere = cmds.polySphere(name="other_mesh")[0]
    cmds.select(sphere, replace=True)
    other = controller.add_model_from_selection()
    rig_card = window.setup_view.plan_banner.rig_card
    REPORT["checks"]["dissimilar_mesh_blocks_rig"] = bool(
        other and controller.session.mesh_similarity.score < 80 and
        rig_card.isVisible() and not rig_card.start_button.isEnabled() and
        "can't be transferred" in rig_card.reason_label.text())
    REPORT["checks"]["blocked_rig_does_not_start"] = window.start_plan("rig") is None and controller.rig_fit() is None
    _grab(window, "07_setup_dissimilar")
    controller.remove_model(other.character_id)
    cmds.delete(sphere)
    REPORT["checks"]["copy_moved"] = abs(cmds.getAttr(copy + ".translateX") - 200.0) < 1e-6
    cmds.select(copy, replace=True)
    mesh_model = controller.add_model_from_selection()
    REPORT["checks"]["copy_mesh_only"] = bool(
        mesh_model and mesh_model.has_mesh and not mesh_model.has_rig and not mesh_model.has_anim)
    REPORT["checks"]["rig_then_animation_plan"] = controller.session.plan.kind == "rig_then_animation"
    REPORT["checks"]["rig_plan_source_a"] = controller.session.source is model_a
    REPORT["checks"]["rig_four_steps"] = len(window.stepper.buttons) == 4
    REPORT["checks"]["similar_mesh_enables_rig"] = bool(
        controller.session.mesh_similarity.score > 99 and rig_card.start_button.isEnabled())
    REPORT["checks"]["animation_waits_for_rig"] = not window.setup_view.plan_banner.animation_card.start_button.isEnabled()
    _grab(window, "07_setup_similar")
    window.start_plan()
    REPORT["checks"]["start_opens_rig"] = window.stack.currentWidget() is window.rig_view
    fit = controller.rig_fit()
    REPORT["checks"]["rig_fit_created"] = bool(fit and cmds.objExists(fit.root))
    fitted_root = fit.root if fit else None
    if fit:
        # Mesh-normalised fitting preserves source joint positions on a scaled copy.
        from rigflow.scene.rest_pose import rest_pose
        with rest_pose(fit.source_joints):
            source_points = [cmds.xform(j, q=True, ws=True, t=True) for j in fit.source_joints]
        points = [cmds.xform(j, q=True, ws=True, t=True) for j in fit.joints]
        REPORT["checks"]["rig_fit_scale"] = round(fit.scale, 4)
        REPORT["checks"]["rig_fit_inside_mesh"] = all(
            abs(b[i] - (a[i] * .8 + (200 if i == 0 else 0))) < 1e-3
            for a, b in zip(source_points, points) for i in range(3))
    _grab(window, "07_rig_fit")
    _viewport_diagnostics(window, "rig_fit")
    window.rig_view.bind_button.click()
    REPORT["checks"]["bind_opens_match"] = window.stack.currentWidget() is window.match_view
    REPORT["checks"]["started_rig_steps_preserved"] = window.stepper.names == ["Setup", "Rig", "Match", "Transfer"]
    REPORT["checks"]["bound_rig_detected"] = bool(mesh_model and mesh_model.has_rig)
    REPORT["checks"]["copy_has_skin_cluster"] = bool(
        cmds.ls(cmds.listHistory(copy) or [], type="skinCluster"))
    second_clip = controller.session.active_clip
    REPORT["checks"]["rig_mapping_ok"] = bool(second_clip and controller.validate(second_clip.clip_id).ok)
    if second_clip:
        window.open_transfer(second_clip.clip_id)
    REPORT["checks"]["rig_preview_started"] = bool(window.transfer_view._preview_ready)
    _grab(window, "08_rig_transfer")
    _viewport_diagnostics(window, "rig_transfer")
    second_result = controller.bake(second_clip.clip_id) if second_clip else None
    REPORT["checks"]["rig_bake_succeeded"] = second_result is not None
    fitted_hips = second_clip.mapping.matches["Hips"].destination if second_clip else fitted_root
    REPORT["checks"]["fitted_hips_has_keys"] = bool(
        fitted_hips and (cmds.keyframe(fitted_hips, query=True, keyframeCount=True) or 0) > 0)
    REPORT["checks"]["rig_destination_stays_b"] = controller.session.destination is mesh_model
    REPORT["checks"]["rig_animation_marked_transferred"] = bool(
        mesh_model and mesh_model.has_anim and mesh_model.anim.transferred)
    _grab(window, "09_rig_baked")

    window.open_match(second_clip.clip_id)
    close_baseline = controller._definition_viewport
    window.close()
    REPORT["checks"]["close_restores_main_viewport"] = restored_to(close_baseline)
    REPORT["checks"]["close_releases_definition"] = controller._definition_viewport is None
    REPORT["checks"]["no_unexpected_service_errors"] = not REPORT.get("service_errors")
    _pump(0.3)
    REPORT["ok"] = all(REPORT["checks"].get(k) for k in (
        "rig_valid", "model_valid", "clip_added", "mapping_ok", "preview_started",
        "facial_untouched", "source_untouched", "jaw_control_drives_jaw", "hips_moved_up",
        "undo_removed_layer", "redo_restored_layer", "manual_match",
        "matching_viewports_embedded", "matching_hidden_viewports_released",
        "review_viewports_embedded", "review_hidden_viewports_released",
        "model_a_detected", "model_b_detected", "animation_plan", "animation_source_a", "start_opens_match",
        "model_b_removed", "copy_mesh_only", "rig_then_animation_plan", "rig_plan_source_a", "rig_four_steps",
        "start_opens_rig", "rig_fit_created", "bind_opens_match", "bound_rig_detected", "copy_has_skin_cluster",
        "rig_mapping_ok", "rig_preview_started", "rig_bake_succeeded", "fitted_hips_has_keys",
        "rig_destination_stays_b", "rig_animation_marked_transferred", "copy_moved", "rig_fit_inside_mesh",
        "rig_fit_viewports_embedded", "rig_fit_hidden_viewports_released",
        "rig_transfer_viewports_embedded", "rig_transfer_hidden_viewports_released",
        "dissimilar_mesh_blocks_rig", "blocked_rig_does_not_start", "similar_mesh_enables_rig",
        "animation_waits_for_rig", "started_rig_steps_preserved",
        "match_main_isolated", "match_joint_xray", "match_no_embedded_panels", "slot_first_waits",
        "wrong_model_rejected", "slot_first_assigned", "switch_isolates_b", "joint_first_assigned",
        "assigned_slot_selects_scene", "display_bones", "display_mesh", "display_both", "match_minimum_size",
        "back_restores_main_viewport", "transfer_restores_main_viewport", "close_restores_main_viewport",
        "close_releases_definition",
        "disabled_isolate_restored",
        "no_unexpected_service_errors",
    ))


def main():
    try:
        run()
    except Exception:
        REPORT["errors"].append(traceback.format_exc())
        REPORT["ok"] = False
        print(traceback.format_exc())
    finally:
        with open(os.path.join(OUT_DIR, "report.json"), "w") as handle:
            json.dump(REPORT, handle, indent=2, default=str)
        print("[rigflow-gui-check] report written to", os.path.join(OUT_DIR, "report.json"))
        if os.environ.get("RIGFLOW_GUI_KEEP_OPEN") != "1":
            from maya import cmds

            cmds.evalDeferred("import maya.cmds as cmds; cmds.quit(force=True)")


main()
