"""Deterministic in-memory scene for previews; no tests or Maya dependency."""
from __future__ import annotations

from pathlib import Path
from rigflow.animation.clip import AnimationClip, ClipStatus
from rigflow.core.session import ModelInfo, RigInfo
from rigflow.mapping.matcher import label_skeleton
from rigflow.skeleton.model import JointInfo, Skeleton
from rigflow.ui.controller import ControllerBase, action
from rigflow.ui.qt import QtCore


def demo_skeleton(source=True):
    """A Mixamo body and a smaller custom body, including unequal spine chains."""
    spec = [
        ("Hips", None, (0, 100, 0)), ("Spine", "Hips", (0, 110, 0)),
        ("Spine1", "Spine", (0, 122, 0)), ("Spine2", "Spine1", (0, 135, 0)),
        ("Neck", "Spine2", (0, 150, 0)), ("Head", "Neck", (0, 160, 0)),
    ]
    for side, sign in (("Left", 1), ("Right", -1)):
        for part, parent, pos in (
            ("Shoulder", "Spine2", (5, 148, 0)), ("Arm", side + "Shoulder", (18, 148, 0)),
            ("ForeArm", side + "Arm", (45, 148, 0)), ("Hand", side + "ForeArm", (72, 148, 0)),
            ("UpLeg", "Hips", (9, 95, 0)), ("Leg", side + "UpLeg", (9, 52, 0)),
            ("Foot", side + "Leg", (9, 8, 0)), ("ToeBase", side + "Foot", (9, 2, 12)),
        ):
            spec.append((side + part, parent, (pos[0] * sign, pos[1], pos[2])))
    if source:
        rename = {n: "mixamorig:" + n for n, _, _ in spec}
        scale = 1.0
    else:
        rename = dict(Hips="pelvis_JNT", Spine="spine_01_JNT", Spine1="spine_02_JNT",
                      Spine2="chest_JNT", Neck="neck_JNT", Head="head_JNT")
        for side, prefix in (("Left", "l_"), ("Right", "r_")):
            for part, name in (("Shoulder", "clavicle"), ("Arm", "shoulder"),
                               ("ForeArm", "elbow"), ("Hand", "wrist"), ("UpLeg", "hip"),
                               ("Leg", "knee"), ("Foot", "ankle"), ("ToeBase", "ball")):
                rename[side + part] = prefix + name + "_JNT"
        scale = 0.7
    return Skeleton([JointInfo(rename[n], rename.get(p), tuple(v * scale for v in pos), animated=source)
                     for n, p, pos in spec], name="Mixamo" if source else "Custom studio rig")


class FakeController(ControllerBase):
    """Implements the entire view contract with a tiny simulated timeline."""

    def __init__(self, session=None, parent=None):
        super().__init__(session, parent)
        self._frame = 1.0
        self._loop = True
        self._preview_id = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(42)
        self._timer.timeout.connect(self._tick)

    @action()
    def set_model_from_selection(self):
        model = ModelInfo("Nova · destination", ["Nova_body", "Nova_outfit"], 24816, True,
                          "pelvis_JNT", "Skinned geometry detected")
        self.session.set_model(model)
        return model

    @action()
    def import_model(self, path):
        model = self.set_model_from_selection()
        model.name = Path(path).stem
        self.session.set_model(model)
        return model

    @action()
    def set_rig_from_selection(self):
        for clip in self.session.clips:
            self.stop_preview(clip.clip_id)
        skeleton = demo_skeleton(False)
        labeling = label_skeleton(skeleton)
        rig = RigInfo("Nova skeleton", skeleton.main_root(), skeleton, labeling,
                      labeling.convention, warnings=list(labeling.notes))
        self.session.set_rig(rig)
        for clip in self.session.clips:
            self.auto_map(clip.clip_id)
        return rig

    @action()
    def import_rig(self, path):
        return self.set_rig_from_selection()

    def _new_clip(self, name, path=None):
        skeleton = demo_skeleton(True)
        return AnimationClip(name=name, source_path=path, source_root=skeleton.main_root(),
                             source_skeleton=skeleton, convention=label_skeleton(skeleton).convention,
                             frame_range=(1.0, 120.0), fps=24.0)

    @action("Loading demo animation…")
    def add_animation_from_file(self, path):
        clip = self._new_clip(Path(path).stem, path)
        self.session.add_clip(clip)
        if self.session.destination_ready:
            self.auto_map(clip.clip_id)
        self.session.status("{} added. Review the joint mapping before transfer.".format(clip.name), "success")
        return clip

    @action()
    def add_animation_from_scene(self, root: str):
        clip = self._new_clip("Scene · " + root)
        self.session.add_clip(clip)
        if self.session.destination_ready:
            self.auto_map(clip.clip_id)
        return clip

    def list_scene_skeleton_roots(self):
        return ["mixamorig:Hips", "walk_cycle:Hips"]

    def preview_message(self, clip_id):
        return "Demo playback · nothing baked yet"

    @action()
    def remove_clip(self, clip_id):
        self.stop_preview(clip_id)
        return self.session.remove_clip(clip_id)

    @action()
    def replace_animation(self, clip_id, path):
        self._clip(clip_id)
        self.stop_preview(clip_id)
        clip = self._new_clip(Path(path).stem, path)
        self.session.replace_clip(clip_id, clip)
        if self.session.destination_ready:
            self.auto_map(clip_id)
        return clip

    @action(default=False)
    def start_preview(self, clip_id):
        if not self.validate(clip_id).ok:
            self.session.status("Resolve mapping errors before preview.", "error")
            return False
        if self._preview_id:
            self.stop_preview(self._preview_id)
        self._preview_id = clip_id
        clip = self._clip(clip_id)
        self._frame = clip.frame_range[0]
        clip.status = ClipStatus.PREVIEWING
        self.session.clip_updated(clip_id)
        return True

    @action(default=False)
    def stop_preview(self, clip_id):
        if self._preview_id == clip_id:
            self.pause()
            self._preview_id = None
            clip = self.session.get_clip(clip_id)
            if clip and clip.status == ClipStatus.PREVIEWING:
                self._refresh(clip)
        return True

    @action("Transferring demo animation…")
    def bake(self, clip_id, to_layer=True):
        if not self.validate(clip_id).ok:
            self.session.status("Resolve mapping errors before transfer.", "error")
            return None
        self.stop_preview(clip_id)
        clip = self._clip(clip_id)
        clip.result = {"backend": "demo", "layer": "rigflow_transfer" if to_layer else None,
                       "frame_range": clip.frame_range, "warnings": []}
        clip.status = ClipStatus.TRANSFERRED
        self.session.clip_updated(clip_id)
        self.session.status("{} transferred (demo).".format(clip.name), "success")
        return clip.result

    def set_frame(self, frame):
        self._frame = float(frame)
        return self._frame

    def current_frame(self):
        return self._frame

    def play(self):
        self._timer.start()
        return True

    def pause(self):
        self._timer.stop()
        return True

    def is_playing(self):
        return self._timer.isActive()

    def set_loop(self, enabled):
        self._loop = bool(enabled)

    def _tick(self):
        clip = self.session.get_clip(self._preview_id)
        if clip is None:
            self.pause()
            return
        start, end = clip.frame_range
        self._frame += 1
        if self._frame > end:
            self._frame = start if self._loop else end
            if not self._loop:
                self.pause()
