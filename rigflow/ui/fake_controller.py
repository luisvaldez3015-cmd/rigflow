"""Deterministic in-memory scene for previews; no tests or Maya dependency."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from rigflow.core.character import Character, MeshSlot, RigSlot, AnimSlot
from rigflow.animation.clip import AnimationClip, ClipStatus
from rigflow.core.session import ModelInfo, RigInfo
from rigflow.core.similarity import MeshSimilarity
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
        self.scripted_pair = ("mixamorig:LeftHand", "l_wrist_JNT")
        self._selection_consumed = False

    def _file_model(self, path):
        """Stem rules: mixamo/walk/jump/run/anim = animated rig only;
        statue/mesh/obj or .obj = unskinned mesh; hero = all three;
        anything else = skinned mesh and unanimated rig (Nova).
        Rules are checked in this order, matching the preview contract.
        """
        stem = Path(path).stem.lower()
        animated = any(word in stem for word in ("mixamo", "walk", "jump", "run", "anim"))
        mesh_only = not animated and (any(word in stem for word in ("statue", "mesh", "obj")) or
                                      Path(path).suffix.lower() == ".obj")
        hero = not animated and not mesh_only and "hero" in stem
        skeleton = demo_skeleton(animated or hero)
        labels = label_skeleton(skeleton)
        return Character(Path(path).stem, source_path=str(path),
            mesh=None if animated else MeshSlot([Path(path).stem + "_body"], 24816, not mesh_only),
            rig=None if mesh_only else RigSlot(skeleton.main_root(), skeleton, labels,
                                               labels.convention, list(labels.notes)),
            anim=AnimSlot((1.0, 120.0), 24.0, len(skeleton)) if animated or hero else None)

    def mesh_similarity(self, a, b):
        """Deterministic preview rules: twin/copy/same = 96%, statue/other = 41%,
        otherwise 92%. 'head' marks Head as differing. Similarity stems are
        independent of slot detection (.obj still means a mesh-only model).
        """
        key = (a.character_id, b.character_id)
        if key not in self._similarity_cache:
            stems = " ".join(Path(c.source_path or c.name).stem.lower() for c in (a, b))
            score = (96.0 if any(w in stems for w in ("twin", "copy", "same")) else
                     41.0 if any(w in stems for w in ("statue", "other")) else 92.0)
            self._similarity_cache[key] = MeshSimilarity(score, score >= 80, ["Head"] if "head" in stems else [])
        return self._similarity_cache[key]

    @action("Adding demo model…")
    def add_model_from_file(self, path):
        """Detect by stem: mixamo/walk/jump/run/anim → rig + animation;
        statue/mesh/obj or .obj → mesh only; hero → all three;
        otherwise → skinned mesh + rig, without animation.
        """
        return self.session.add_character(self._file_model(path))

    @action()
    def add_model_from_selection(self):
        character = self._file_model("Nova.ma")
        character.source_path = None
        return self.session.add_character(character)

    @action()
    def add_model_from_scene(self, node):
        character = self._file_model("walk.fbx" if "Hips" in node else node)
        character.name, character.source_path = node.rsplit("|", 1)[-1], None
        return self.session.add_character(character)

    @action(default=list)
    def list_scene_candidates(self):
        owned = {c.name for c in self.session.characters}
        return [n for n in ("mixamorig:Hips", "Nova", "Statue_mesh") if n not in owned]

    def _release_model(self, character_id):
        self._stop_model_previews()
        self.cancel_rig_fit()
        clip_id = self._character_clips.pop(character_id, None)
        if clip_id:
            self.remove_clip(clip_id)
        self._forget_destination(character_id)
        self.session.set_model(None)
        self.session.set_rig(None)

    @action()
    def remove_model(self, character_id):
        self._release_model(character_id)
        return self.session.remove_character(character_id)

    @action()
    def replace_model_from_file(self, character_id, path):
        character = self._file_model(path)
        self._release_model(character_id)
        return self.session.replace_character(character_id, character)

    def _model_clip(self, character):
        return AnimationClip(name=character.name, source_path=character.source_path,
            source_root=character.rig.root, source_skeleton=character.rig.skeleton,
            convention=character.rig.convention, frame_range=character.anim.frame_range,
            fps=character.anim.fps)

    @action("Fitting demo rig…")
    def fit_rig(self):
        if self._fit is None:
            self._fit = SimpleNamespace(root="Statue_Hips", joints=list(demo_skeleton(False)),
                                        scale=0.7, skin_clusters=[], warnings=[])
            self._fit_destination_id = self.session.destination.character_id
        return self._fit

    @action()
    def refit_rig(self):
        self.cancel_rig_fit()
        return self.fit_rig()

    @action(default=False)
    def cancel_rig_fit(self):
        self._fit = None
        self._fit_destination_id = None
        return True

    @action("Binding demo rig…")
    def bind_rig(self):
        if self._fit is None:
            return None
        destination = self.session.get_character(self._fit_destination_id)
        skeleton = demo_skeleton(False)
        labels = label_skeleton(skeleton)
        destination.rig = RigSlot(skeleton.main_root(), skeleton, labels, labels.convention)
        destination.mesh.skinned = True
        self._fit.skin_clusters = ["rigflow_skin1"]
        self._fit = None
        self._fit_destination_id = None
        started_steps = self.session.started_steps
        self.session.character_updated(destination.character_id)
        result = self.start_plan() if self.session.plan.transfers_animation else {"step": "setup"}
        self.session.started_steps = started_steps
        return result

    def begin_selection(self, clip_id):
        super().clear_selected_pair(clip_id)
        self._selection_consumed = False

    def selected_pair(self, clip_id):
        if not self._selection_consumed:
            self._selected_pairs[clip_id] = self.scripted_pair
            self._selection_consumed = True
        return super().selected_pair(clip_id)

    def clear_selected_pair(self, clip_id):
        super().clear_selected_pair(clip_id)
        self._selection_consumed = True

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
        self._clip_destinations.pop(clip_id, None)
        self._source_labels.pop(clip_id, None)
        self._selected_pairs.pop(clip_id, None)
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
                       "frame_range": clip.frame_range, "warnings": [],
                       "baked_joints": sorted(clip.mapping.destination_joints_used()),
                       "verification": {"max_bone_length_error": 0.0, "elapsed_s": 0.12}}
        clip.status = ClipStatus.TRANSFERRED
        self._mark_destination_animation(clip, clip.result)
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
