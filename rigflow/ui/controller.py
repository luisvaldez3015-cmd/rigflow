"""UI boundary: pure mapping actions and lazily loaded Maya services.

All public actions are guarded: failures become Session STATUS events. Maya
scene mutations stay on the UI thread and inside an undo chunk. The extra
viewport methods keep scene imports out of the widgets as required by the
architecture. Playback and private cameras have no scene-service contracts,
so their small Maya adapters live here.
"""
from __future__ import annotations

import importlib
from dataclasses import asdict
from functools import wraps
from pathlib import Path

from rigflow.animation.clip import AnimationClip, ClipStatus
from rigflow.core import compat
from rigflow.core.errors import RigFlowError, SceneError, MappingError
from rigflow.core.logging import get_logger
from rigflow.core.session import Session, ModelInfo, RigInfo
from rigflow.core.character import Character, MeshSlot, RigSlot, AnimSlot
from rigflow.mapping.matcher import auto_map, label_skeleton
from rigflow.mapping.validation import ValidationReport, validate_mapping
from rigflow.mapping.presets import save_mapping, load_mapping
from rigflow.ui.qt import QtCore, QtGui, QtWidgets, Signal

LOG = get_logger(__name__)


def action(message=None, default=None):
    """Convert service exceptions into status events; bracket long operations."""
    def decorate(function):
        @wraps(function)
        def run(self, *args, **kwargs):
            outer = self._depth == 0
            self._depth += 1
            if message and outer:
                self.operation_started.emit(message)
                QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            try:
                return function(self, *args, **kwargs)
            except Exception as exc:
                if not isinstance(exc, (RigFlowError, ImportError)):
                    LOG.exception("UI action failed: %s", function.__name__)
                text = ("Service unavailable: " + str(exc)) if isinstance(exc, ImportError) else str(exc)
                self.session.status(text, "error")
                return default() if callable(default) else default
            finally:
                self._depth -= 1
                if message and outer:
                    self.operation_finished.emit()
        return run
    return decorate


class ControllerBase(QtCore.QObject):
    """View-facing API shared by the Maya and in-memory controllers.

    Methods return their result (or None/False on failure); validate always
    returns a ValidationReport. Session is the source of truth. Views listen
    to Session events and never inspect Maya nodes themselves.
    """
    operation_started = Signal(str)
    operation_finished = Signal()

    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session if session is not None else Session()
        self._depth = 0
        self._selected_pairs = {}
        self._source_labels = {}
        self._character_clips = {}
        self._clip_destinations = {}
        self._fit = None
        self._fit_destination_id = None

    def add_model_from_file(self, path):
        raise NotImplementedError

    def add_model_from_selection(self):
        raise NotImplementedError

    def add_model_from_scene(self, node):
        raise NotImplementedError

    def list_scene_candidates(self):
        raise NotImplementedError

    def remove_model(self, character_id):
        raise NotImplementedError

    def replace_model_from_file(self, character_id, path):
        raise NotImplementedError

    @action()
    def swap_direction(self):
        self._stop_model_previews()
        if self._fit is not None and not self.cancel_rig_fit():
            return None
        return self.session.swap_direction()

    def _stop_model_previews(self):
        for clip in list(self.session.clips):
            if self.stop_preview(clip.clip_id) is False:
                raise SceneError("Could not stop the current preview.")

    def _publish_destination(self):
        destination = self.session.destination
        if destination is None:
            raise SceneError("Add two models with transferable content first.")
        mesh, rig = destination.mesh, destination.rig
        self.session.set_model(ModelInfo(destination.name, list(mesh.meshes), mesh.vertex_count,
            mesh.skinned, rig.root if rig else None) if destination.has_mesh else None)
        self.session.set_rig(RigInfo(destination.name, rig.root, rig.skeleton, rig.labeling,
            rig.convention, warnings=list(rig.warnings)) if destination.has_rig else None)

    @action("Starting proposed process…")
    def start_plan(self):
        if not self.session.plan.ready:
            raise SceneError(self.session.plan.message)
        self._stop_model_previews()
        self._publish_destination()
        if self.session.plan.first_step == "rig":
            return {"step": "rig"} if self.fit_rig() is not None else None
        source = self.session.source
        clip = self.session.get_clip(self._character_clips.get(source.character_id))
        if clip is None:
            clip = self._model_clip(source)
            self._character_clips[source.character_id] = clip.clip_id
            self.session.add_clip(clip)
        else:
            self.session.set_active_clip(clip.clip_id)
        destination = self.session.destination
        target = (destination.character_id, destination.rig.skeleton)
        if self._clip_destinations.get(clip.clip_id) != target:
            clip.mapping = None
        self._clip_destinations[clip.clip_id] = target
        if self.auto_map(clip.clip_id) is None:
            return None
        return {"step": "match", "clip_id": clip.clip_id}

    def fit_rig(self):
        raise NotImplementedError

    def refit_rig(self):
        raise NotImplementedError

    def cancel_rig_fit(self):
        raise NotImplementedError

    @action()
    def rig_fit(self):
        return self._fit

    @action(default=list)
    def rig_viewport_nodes(self):
        destination = self.session.get_character(self._fit_destination_id) or self.session.destination
        meshes = list(destination.mesh.meshes) if destination and destination.has_mesh else []
        return meshes + ([self._fit.root] if self._fit else [])

    def bind_rig(self):
        raise NotImplementedError

    def _forget_destination(self, character_id):
        """A removed/replaced destination invalidates the mappings and results made against it."""
        for clip_id, (destination_id, _) in list(self._clip_destinations.items()):
            if destination_id != character_id:
                continue
            clip = self.session.get_clip(clip_id)
            if clip is not None:
                clip.mapping, clip.result, clip.notes = None, {}, []
                clip.status = ClipStatus.IMPORTED
                self.session.clip_updated(clip_id)
            self._clip_destinations.pop(clip_id, None)

    def _mark_destination_animation(self, clip, result):
        destination = self.session.destination
        if destination is not None:
            destination.anim = AnimSlot(result.get("frame_range", clip.frame_range), clip.fps,
                                       len(result.get("baked_joints", [])), transferred=True)
            self.session.character_updated(destination.character_id)

    def begin_selection(self, clip_id):
        """Start a fresh Match selection lifetime."""
        self.clear_selected_pair(clip_id)

    def remember_selected(self, clip_id, joint, destination=False):
        pair = list(self._selected_pairs.get(clip_id, (None, None)))
        pair[int(destination)] = joint
        self._selected_pairs[clip_id] = tuple(pair)

    def clear_selected_pair(self, clip_id):
        self._selected_pairs.pop(clip_id, None)

    def selected_pair(self, clip_id):
        """Return remembered source/destination joints selected in Maya."""
        return self._selected_pairs.get(clip_id, (None, None))

    def selection_role(self, clip_id, source=None, destination=None):
        """Resolve A's role first, then B's, independently of the table selection."""
        clip = self._clip(clip_id)
        rig = self.session.rig
        if clip.source_skeleton is None:
            return rig.labeling.role_of(destination) if rig and rig.labeling else None
        cached = self._source_labels.get(clip_id)
        if cached is None or cached[0] is not clip.source_skeleton:
            cached = (clip.source_skeleton, label_skeleton(clip.source_skeleton))
            self._source_labels[clip_id] = cached
        role = cached[1].role_of(source)
        return role or (rig.labeling.role_of(destination) if rig and rig.labeling else None)

    def _clip(self, clip_id):
        clip = self.session.get_clip(clip_id)
        if clip is None:
            raise SceneError("Animation no longer exists.", "Add an animation first.")
        return clip

    def _mapping(self, clip_id):
        clip = self._clip(clip_id)
        if clip.mapping is None:
            raise MappingError("No mapping yet.", "Choose a destination rig and run Auto-match.")
        return clip.mapping

    def _refresh(self, clip):
        report = self.validate(clip.clip_id)
        clip.status = ClipStatus.MAPPED if report.ok else ClipStatus.NEEDS_REVIEW
        self.session.clip_updated(clip.clip_id)
        return report

    @action("Matching joints…")
    def auto_map(self, clip_id):
        """Recompute automatic matches while retaining manual overrides/exclusions."""
        clip = self._clip(clip_id)
        if not self.session.destination_ready or clip.source_skeleton is None:
            raise SceneError("Choose a destination rig and a source skeleton before matching.")
        if self.stop_preview(clip_id) is False:
            return None
        mapping, source, _ = auto_map(clip.source_skeleton, self.session.rig.skeleton, clip.mapping)
        clip.mapping = mapping
        clip.convention = source.convention
        self._refresh(clip)
        return mapping

    @action()
    def set_manual_match(self, clip_id, role, source, destination):
        """Assign an existing source/destination pair to the selected role."""
        clip = self._clip(clip_id)
        mapping = self._mapping(clip_id)
        if ((source is not None and source not in clip.source_skeleton) or
                (destination is not None and destination not in self.session.rig.skeleton)):
            raise MappingError("Select a joint from each hierarchy first.")
        if self.stop_preview(clip_id) is False:
            return None
        match = mapping.set_manual(role, source, destination)
        self._refresh(clip)
        return match

    @action()
    def clear_manual(self, clip_id, role=None):
        """Clear one or all manual overrides, then recover automatic results."""
        mapping = self._mapping(clip_id)
        if self.stop_preview(clip_id) is False:
            return None
        if role is None:
            mapping.clear_all_manual()
        else:
            mapping.clear_manual(role)
        return self.auto_map(clip_id)

    @action()
    def set_excluded(self, clip_id, role, excluded):
        """Exclude/reinclude a role. Required exclusions are validation errors."""
        if self.stop_preview(clip_id) is False:
            return None
        self._mapping(clip_id).set_excluded(role, excluded)
        return self._refresh(self._clip(clip_id))

    def validate(self, clip_id) -> ValidationReport:
        """Return blocking errors and nonblocking warnings, including missing state."""
        try:
            clip = self._clip(clip_id)
            if not self.session.destination_ready:
                raise MappingError("Choose a destination rig.")
            if clip.source_skeleton is None:
                raise MappingError("Source skeleton is unavailable.")
            return validate_mapping(self._mapping(clip_id), clip.source_skeleton, self.session.rig.skeleton)
        except Exception as exc:
            report = ValidationReport()
            report.add("error", str(exc))
            return report

    @action()
    def frame_range(self, clip_id):
        """Return the source clip's inclusive (start, end) frame range."""
        return self._clip(clip_id).frame_range

    @action("Saving mapping preset…")
    def save_preset(self, clip_id, path):
        """Write the current mapping to a RigFlow JSON preset."""
        result = save_mapping(self._mapping(clip_id), path)
        self.session.status("Mapping preset saved.", "success")
        return result

    @action("Loading mapping preset…")
    def load_preset(self, clip_id, path):
        """Load a preset and validate its joint names against both skeletons."""
        mapping = load_mapping(path)
        if self.stop_preview(clip_id) is False:
            return None
        clip = self._clip(clip_id)
        clip.mapping = mapping
        return self._refresh(clip)

    @action()
    def open_url(self, url):
        """Open documentation or the repository in the default browser."""
        if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)):
            raise RigFlowError("Could not open browser.", url)
        return True

    @action(default=dict)
    def environment(self):
        """Return compat.environment_summary() for About and support reports."""
        return compat.environment_summary()

    # Scene adapters. These signatures define the substitutable view contract.
    def set_model_from_selection(self):
        """Inspect selected destination mesh transforms; report empty selections."""
        raise NotImplementedError

    def import_model(self, path):
        """Import .fbx/.ma/.mb and publish inspected destination geometry."""
        raise NotImplementedError

    def set_rig_from_selection(self):
        """Read a selected skeleton (or skinned mesh's skeleton) at rest."""
        raise NotImplementedError

    def import_rig(self, path):
        """Import a skeleton file, then label and publish its detected rig."""
        raise NotImplementedError

    def add_animation_from_file(self, path):
        """Import source animation, register a clip and attempt automatic matching."""
        raise NotImplementedError

    def add_animation_from_scene(self, root: str):
        """Register animation on an explicitly chosen existing scene root."""
        raise NotImplementedError

    def list_scene_skeleton_roots(self):
        """Return available source skeleton roots for a scene-root picker."""
        raise NotImplementedError

    def remove_clip(self, clip_id):
        """Cancel preview, remove owned imports, and remove the session clip."""
        raise NotImplementedError

    def replace_animation(self, clip_id, path):
        """Replace an imported source only after its new file loads successfully."""
        raise NotImplementedError

    def start_preview(self, clip_id):
        """Validate and prepare a live retarget. Return True on success."""
        raise NotImplementedError

    def stop_preview(self, clip_id):
        """Remove live retarget nodes without baking. Return False on failure."""
        raise NotImplementedError

    def preview_message(self, clip_id):
        """Describe what the prepared backend can display before committing."""
        return "Live preview · nothing baked yet"

    def bake(self, clip_id, to_layer=True):
        """Bake the validated clip and publish TRANSFERRED and backend results."""
        raise NotImplementedError

    def set_frame(self, frame):
        """Set the Maya timeline (a float, preserving subframes)."""
        raise NotImplementedError

    def current_frame(self):
        """Return the current timeline position, or None on failure."""
        raise NotImplementedError

    def play(self):
        """Start timeline playback within the active preview's range."""
        raise NotImplementedError

    def pause(self):
        """Pause without changing the current timeline position."""
        raise NotImplementedError

    def is_playing(self):
        """Return whether timeline playback is active."""
        raise NotImplementedError

    def set_loop(self, enabled):
        """Toggle playback looping (adapter extension absent in scene contract)."""
        raise NotImplementedError

    def create_viewport(self, parent_name, camera="persp", isolate=()):
        """Return a modelPanel name, or None for a standalone placeholder."""
        return None

    def viewport_nodes(self, clip_id, destination=False):
        """Return nodes to isolate; destination geometry is optional."""
        if destination:
            rig, model = self.session.rig, self.session.model
            return ([rig.root] if rig else []) + (model.meshes if model else [])
        clip = self.session.get_clip(clip_id)
        return [clip.source_root] if clip and clip.source_root else []

    def viewport_container(self, panel):
        """Return the Maya layout that hosts ``panel`` (the widget to embed), or None."""
        return None

    def delete_viewport(self, panel):
        """Release a modelPanel owned by a ViewportPanel."""
        return None

    def frame_viewport(self, panel, nodes):
        """Frame once after the embedded panel receives its final size."""
        return None

    def create_demo_scene(self):
        """Build the sample characters and load them as destination (Maya only)."""
        self.session.status("The demo scene can only be created inside Maya.", "warning")
        return None

    @action()
    def shutdown(self):
        """Pause playback and release all live preview resources."""
        self.cancel_rig_fit()
        self.pause()
        for clip in self.session.clips:
            self.stop_preview(clip.clip_id)


class Controller(ControllerBase):
    """Maya service orchestrator; construction is safe outside Maya."""

    def __init__(self, session=None, parent=None):
        super().__init__(session, parent)
        self._imports = {}
        self._previews = {}
        self._playback_state = None
        self._viewport_cameras = {}
        self._last_selection = {}
        self._selection_skeletons = {}
        self._model_imports = {}

    def _rig_slot(self, root):
        skeleton = self._service("skeleton_reader").read_skeleton_rest(root)
        labeling = label_skeleton(skeleton)
        return RigSlot(root, skeleton, labeling, labeling.convention, list(labeling.notes))

    def _character(self, scan, result=None):
        return Character(scan.name, source_path=result.path if result else None,
            namespace=result.namespace if result else None,
            mesh=MeshSlot([m.transform for m in scan.meshes], sum(m.vertex_count for m in scan.meshes),
                          any(m.skinned for m in scan.meshes)) if scan.meshes else None,
            rig=self._rig_slot(scan.skeleton.root) if scan.skeleton else None,
            anim=AnimSlot(scan.frame_range, scan.fps, scan.skeleton.animated_joints) if scan.has_anim else None,
            notes=list(scan.warnings))

    def _load_model(self, path):
        importer = self._service("importer")
        result = importer.import_file(path)
        try:
            character = self._character(self._service("characters").scan_import(result), result)
            if not character.usable:
                raise SceneError("No mesh or readable skeleton detected.")
            return character, result
        except Exception:
            importer.remove_import(result)
            raise

    @action("Adding model…")
    def add_model_from_file(self, path):
        with self._undo("RigFlow Add Model"):
            character, result = self._load_model(path)
            self._model_imports[character.character_id] = result
            return self.session.add_character(character)

    @action("Detecting selected model…")
    def add_model_from_selection(self):
        nodes = self._service("inspector").selection()
        if not nodes:
            raise SceneError("Nothing selected.", "Select a mesh or a skeleton root in Maya.")
        character = self._character(self._service("characters").scan_nodes(nodes, nodes[0].rsplit("|", 1)[-1]))
        if not character.usable:
            raise SceneError("No mesh or readable skeleton detected.")
        return self.session.add_character(character)

    @action("Detecting scene model…")
    def add_model_from_scene(self, node):
        character = self._character(self._service("characters").scan_nodes([node], node.rsplit("|", 1)[-1]))
        if not character.usable:
            raise SceneError("No mesh or readable skeleton detected.")
        return self.session.add_character(character)

    @action(default=list)
    def list_scene_candidates(self):
        inspector = self._service("inspector")
        owned = set()
        for character in self.session.characters:
            if character.has_mesh:
                owned.update(character.mesh.meshes)
            if character.has_rig:
                owned.update(character.rig.skeleton)
                owned.add(character.rig.root)
            result = self._model_imports.get(character.character_id)
            if result:
                owned.update(result.new_nodes)
        short_owned = {node.rsplit("|", 1)[-1] for node in owned}
        candidates = inspector.find_skeleton_roots() + [m.transform for m in inspector.find_meshes()]
        return list(dict.fromkeys(node for node in candidates if node not in owned and
            node.rsplit("|", 1)[-1] not in short_owned and not inspector._is_helper(node)))

    def _release_model(self, character_id):
        self._stop_model_previews()
        if self._fit is not None and not self.cancel_rig_fit():
            raise SceneError("Could not remove the fitted rig.")
        clip_id = self._character_clips.get(character_id)
        if clip_id and self.session.get_clip(clip_id):
            if self.remove_clip(clip_id) is None:
                raise SceneError("Could not remove the model's animation.")
        result = self._model_imports.get(character_id)
        if result:
            self._service("importer").remove_import(result)
            self._model_imports.pop(character_id, None)
        self._character_clips.pop(character_id, None)
        self._forget_destination(character_id)
        self.session.set_model(None)
        self.session.set_rig(None)

    @action("Removing model…")
    def remove_model(self, character_id):
        if self.session.get_character(character_id) is None:
            return None
        with self._undo("RigFlow Remove Model"):
            self._release_model(character_id)
            return self.session.remove_character(character_id)

    @action("Replacing model…")
    def replace_model_from_file(self, character_id, path):
        with self._undo("RigFlow Replace Model"):
            character, result = self._load_model(path)
            try:
                self._release_model(character_id)
            except Exception:
                self._service("importer").remove_import(result)
                raise
            self._model_imports[character_id] = result
            return self.session.replace_character(character_id, character)

    def _model_clip(self, character):
        return self._source_clip(character.rig.root, character.name,
                                 self._model_imports.get(character.character_id))

    @action("Fitting rig…")
    def fit_rig(self):
        if self._fit is not None:
            return self._fit
        source, destination = self.session.source, self.session.destination
        if not source or not source.has_rig or not destination or not destination.has_mesh:
            raise SceneError("A source rig and destination mesh are required.")
        with self._undo("RigFlow Fit Rig"):
            self._fit = importlib.import_module("rigflow.rigging.transfer").fit_skeleton(
                source.rig.root, destination.mesh.meshes, namespace=destination.namespace)
        self._fit_destination_id = destination.character_id
        return self._fit

    @action("Refitting rig…")
    def refit_rig(self):
        return self.fit_rig() if self.cancel_rig_fit() else None

    @action("Removing fitted rig…", default=False)
    def cancel_rig_fit(self):
        if self._fit is not None:
            with self._undo("RigFlow Cancel Rig Fit"):
                importlib.import_module("rigflow.rigging.transfer").remove_fit(self._fit)
            self._fit = None
            self._fit_destination_id = None
        return True

    @action("Binding rig…")
    def bind_rig(self):
        if self._fit is None:
            raise SceneError("Fit the rig before binding.")
        destination = self.session.get_character(self._fit_destination_id)
        with self._undo("RigFlow Bind Rig"):
            importlib.import_module("rigflow.rigging.transfer").bind_skeleton(self._fit, destination.mesh.meshes)
            destination.rig = self._rig_slot(self._fit.root)
            destination.mesh.skinned = True
        self._fit = None
        self._fit_destination_id = None
        self.session.character_updated(destination.character_id)
        if self.session.destination:
            self._publish_destination()
        return self.start_plan() if self.session.plan.transfers_animation else {"step": "setup"}

    @action(default=lambda: (None, None))
    def selected_pair(self, clip_id):
        clip = self._clip(clip_id)
        rig = self.session.rig
        skeletons = (clip.source_skeleton, rig.skeleton if rig else None)
        if self._selection_skeletons.get(clip_id) != skeletons:
            self._selected_pairs.pop(clip_id, None)
            self._selection_skeletons[clip_id] = skeletons
            self._last_selection.pop(clip_id, None)
        selection = tuple(self._service("inspector").selection())
        if selection != self._last_selection.get(clip_id):
            self._last_selection[clip_id] = selection
            for node in selection:
                for side, skeleton in enumerate(skeletons):
                    if skeleton is None:
                        continue
                    # Inspector returns DAG paths; trees store the skeleton's canonical names.
                    matches = [joint for joint in skeleton if joint == node or
                               joint.rsplit("|", 1)[-1] == node.rsplit("|", 1)[-1]]
                    if len(matches) == 1:
                        self.remember_selected(clip_id, matches[0], bool(side))
        return super().selected_pair(clip_id)

    def begin_selection(self, clip_id):
        self._selected_pairs.pop(clip_id, None)
        self._last_selection.pop(clip_id, None)
        self._selection_skeletons.pop(clip_id, None)

    def clear_selected_pair(self, clip_id):
        super().clear_selected_pair(clip_id)
        # Do not reconsume the same Maya selection on the next timer tick.
        self._last_selection[clip_id] = tuple(self._service("inspector").selection())

    @staticmethod
    def _service(name):
        return importlib.import_module("rigflow.scene." + name)

    @staticmethod
    def _cmds():
        # Playback/time/loop have no service API in architecture.md.
        if not compat.in_maya():
            raise SceneError("This operation is available inside Maya.")
        return importlib.import_module("maya.cmds")

    def _undo(self, name):
        return self._service("undo").undo_chunk(name)

    def _model(self, report, name):
        meshes = report.meshes
        if not meshes:
            raise SceneError("No suitable polygon mesh detected.", "Select mesh transforms or import geometry.")
        root = self._service("inspector").skeleton_root_for_mesh(meshes[0])
        model = ModelInfo(name=name, meshes=[m.transform for m in meshes],
                          vertex_count=sum(m.vertex_count for m in meshes),
                          skinned=any(m.skinned for m in meshes), skeleton_root=root,
                          message="Geometry detected")
        self.session.set_model(model)
        return model

    def _rig(self, root):
        # Stop live connections before sampling a different destination.
        for clip_id in list(self._previews):
            if self.stop_preview(clip_id) is False:
                raise SceneError("Could not release the previous live preview.")
        skeleton = self._service("skeleton_reader").read_skeleton_rest(root)
        labeling = label_skeleton(skeleton)
        rig = RigInfo(name=root.rsplit("|", 1)[-1], root=root, skeleton=skeleton,
                      labeling=labeling, convention=labeling.convention, warnings=list(labeling.notes))
        self.session.set_rig(rig)
        for clip in self.session.clips:
            self.auto_map(clip.clip_id)
        return rig

    def _one_root(self, roots):
        if len(roots) != 1:
            raise SceneError("Detected {} skeleton roots.".format(len(roots)),
                             "Select one skeleton root in the Outliner, then use selection.")
        return roots[0]

    @action("Inspecting destination geometry…")
    def set_model_from_selection(self):
        inspector = self._service("inspector")
        nodes = inspector.selection()
        if not nodes:
            raise SceneError("Nothing selected.", "Select a destination mesh in Maya.")
        return self._model(inspector.inspect_scene(nodes), nodes[0].rsplit("|", 1)[-1])

    @action("Importing destination geometry…")
    def import_model(self, path):
        with self._undo("RigFlow Import Model"):
            result = self._service("importer").import_file(path)
            return self._model(result.report, Path(path).stem)

    @action("Inspecting destination rig…")
    def set_rig_from_selection(self):
        inspector = self._service("inspector")
        nodes = inspector.selection()
        if not nodes:
            raise SceneError("Nothing selected.", "Select a skeleton root or skinned mesh.")
        roots = inspector.find_skeleton_roots(nodes)
        if not roots:
            roots = list(dict.fromkeys(filter(None, (inspector.skeleton_root_for_mesh(m)
                         for m in inspector.find_meshes(nodes)))))
        return self._rig(self._one_root(roots))

    @action("Importing destination rig…")
    def import_rig(self, path):
        with self._undo("RigFlow Import Rig"):
            result = self._service("importer").import_file(path)
            return self._rig(self._one_root([s.root for s in result.report.skeletons]))

    def _source_clip(self, root, name=None, result=None):
        skeleton = self._service("skeleton_reader").read_skeleton_rest(root)
        nodes = list(skeleton)
        io = self._service("animation_io")
        frames = io.animation_range(nodes)
        if frames is None:
            raise SceneError("No animation keys detected on this skeleton.", "Choose an animated source.")
        return AnimationClip(name=name or root.rsplit("|", 1)[-1], source_root=root,
                             source_skeleton=skeleton, frame_range=frames, fps=io.scene_fps(),
                             source_path=result.path if result else None,
                             namespace=result.namespace if result else None,
                             convention=label_skeleton(skeleton).convention)

    def _load_file_clip(self, path):
        importer = self._service("importer")
        result = importer.import_file(path)
        try:
            root = self._one_root([s.root for s in result.report.skeletons])
            return self._source_clip(root, Path(path).stem, result), result
        except Exception:
            importer.remove_import(result)
            raise

    @action("Importing source animation…")
    def add_animation_from_file(self, path):
        with self._undo("RigFlow Import Animation"):
            clip, result = self._load_file_clip(path)
            self._imports[clip.clip_id] = result
            self.session.add_clip(clip)
            if self.session.destination_ready:
                self.auto_map(clip.clip_id)
            return clip

    @action("Reading scene animation…")
    def add_animation_from_scene(self, root: str):
        if self.session.rig and root == self.session.rig.root:
            raise SceneError("Source and destination must be different skeletons.")
        clip = self._source_clip(root)
        self.session.add_clip(clip)
        if self.session.destination_ready:
            self.auto_map(clip.clip_id)
        return clip

    @action(default=list)
    def list_scene_skeleton_roots(self):
        roots = self._service("inspector").find_skeleton_roots()
        return [r for r in roots if not self.session.rig or r != self.session.rig.root]

    @action("Removing animation…")
    def remove_clip(self, clip_id):
        if self.stop_preview(clip_id) is False:
            return None
        result = self._imports.get(clip_id)
        if result is not None:
            with self._undo("RigFlow Remove Animation"):
                self._service("importer").remove_import(result)
            self._imports.pop(clip_id, None)
        self._clip_destinations.pop(clip_id, None)
        self._source_labels.pop(clip_id, None)
        self._selected_pairs.pop(clip_id, None)
        return self.session.remove_clip(clip_id)

    @action("Replacing source animation…")
    def replace_animation(self, clip_id, path):
        """Load successfully before removing the previous clip's owned import."""
        self._clip(clip_id)
        with self._undo("RigFlow Replace Animation"):
            clip, result = self._load_file_clip(path)
            try:
                if self.stop_preview(clip_id) is False:
                    raise SceneError("Could not stop the current preview.")
                old = self._imports.get(clip_id)
                if old:
                    self._service("importer").remove_import(old)
            except Exception:
                self._service("importer").remove_import(result)
                raise
            self._imports[clip_id] = result
            self.session.replace_clip(clip_id, clip)
            if self.session.destination_ready:
                self.auto_map(clip_id)
            return clip

    @action("Preparing live preview…", default=False)
    def start_preview(self, clip_id):
        report = self.validate(clip_id)
        if report.errors:
            raise MappingError("Mapping needs attention.", str(report.errors[0]))
        for existing in list(self._previews):
            if self.stop_preview(existing) is False:
                return False
        clip = self._clip(clip_id)
        base = importlib.import_module("rigflow.retargeting.base")
        retargeting = importlib.import_module("rigflow.retargeting")
        backend = retargeting.get_retargeter()
        request = base.RetargetRequest(mapping=clip.mapping, source_root=clip.source_root,
                                      destination_root=self.session.rig.root, frame_range=clip.frame_range)
        cmds = self._cmds()
        self._playback_state = {
            option: cmds.playbackOptions(query=True, **{option: True})
            for option in ("minTime", "maxTime", "animationStartTime", "animationEndTime", "loop")
        }
        self._playback_state["frame"] = cmds.currentTime(query=True)
        cmds.play(state=False)
        try:
            # prepare() is its own closed undo step; the preview stays live
            # without holding any undo chunk open across user interaction.
            backend.prepare(request)
            self._service("animation_io").set_playback_range(*clip.frame_range)
        except Exception:
            try:
                backend.cleanup()
            finally:
                self._restore_playback()
            raise
        self._previews[clip_id] = backend
        clip.status = ClipStatus.PREVIEWING
        self.session.clip_updated(clip_id)
        if backend.name == "matrix":
            self.session.status(self.preview_message(clip_id), "warning")
        return True

    def preview_message(self, clip_id):
        backend = self._previews.get(clip_id)
        if backend is not None and backend.name == "matrix":
            return "Source playback only · Matrix has no live destination preview. Transfer to bake the animation."
        return super().preview_message(clip_id)

    def viewport_nodes(self, clip_id, destination=False):
        nodes = super().viewport_nodes(clip_id, destination)
        if not destination:
            for character_id, source_clip_id in self._character_clips.items():
                character = self.session.get_character(character_id)
                if source_clip_id == clip_id and character and character.has_mesh:
                    nodes += character.mesh.meshes
            imported = self._imports.get(clip_id)
            if imported is not None:
                nodes += [mesh.transform for mesh in imported.report.meshes]
        return list(dict.fromkeys(nodes))

    def _restore_playback(self):
        if self._playback_state is not None:
            state = dict(self._playback_state)
            frame = state.pop("frame")
            cmds = self._cmds()
            cmds.play(state=False)
            cmds.playbackOptions(**state)
            cmds.currentTime(frame)
            self._playback_state = None

    @action(default=False)
    def stop_preview(self, clip_id):
        backend = self._previews.get(clip_id)
        if backend is not None:
            backend.cleanup()
            self._previews.pop(clip_id, None)
            self._restore_playback()
            clip = self.session.get_clip(clip_id)
            if clip and clip.status == ClipStatus.PREVIEWING:
                self._refresh(clip)
        return True

    @action("Transferring animation…")
    def bake(self, clip_id, to_layer=True):
        if not self.validate(clip_id).ok:
            raise MappingError("Resolve mapping errors before transfer.")
        # Build a fresh request so bake_to_layer always reflects this action.
        if not self.stop_preview(clip_id):
            return None
        clip = self._clip(clip_id)
        base = importlib.import_module("rigflow.retargeting.base")
        backend = importlib.import_module("rigflow.retargeting").get_retargeter()
        request = base.RetargetRequest(mapping=clip.mapping, source_root=clip.source_root,
                                      destination_root=self.session.rig.root,
                                      frame_range=clip.frame_range, bake_to_layer=to_layer)
        # One outer chunk so prepare + bake + cleanup undo as a single step.
        with self._undo("RigFlow: transfer {}".format(clip.name)):
            try:
                backend.prepare(request)
                result = backend.bake()
            finally:
                backend.cleanup()
        clip.result = asdict(result)
        clip.notes = list(result.warnings)
        clip.status = ClipStatus.TRANSFERRED
        self._mark_destination_animation(clip, clip.result)
        self.session.clip_updated(clip_id)
        self.session.status("{} transferred to {}.".format(clip.name, self.session.rig.name), "success")
        return result

    @action()
    def set_frame(self, frame):
        return self._cmds().currentTime(frame)

    @action()
    def current_frame(self):
        return self._cmds().currentTime(query=True)

    @action()
    def play(self):
        self._cmds().play(forward=True)
        return True

    @action()
    def pause(self):
        self._cmds().play(state=False)
        return True

    @action(default=False)
    def is_playing(self):
        return bool(self._cmds().play(query=True, state=True))

    @action()
    def set_loop(self, enabled):
        self._cmds().playbackOptions(loop="continuous" if enabled else "once")

    @action()
    def create_viewport(self, parent_name, camera="persp", isolate=()):
        if not compat.in_maya() or compat.is_batch():
            return None
        viewport = self._service("viewport")
        cmds = self._cmds()
        # Each side must frame independently and leave the artist's camera
        # unchanged. Preview cameras are UI furniture: never on the undo queue.
        with self._service("undo").suspended_undo():
            private_camera = cmds.duplicate(camera, name="rigflowPreviewCamera#")[0]
        panel = None
        try:
            panel = viewport.create_model_panel(parent_name, private_camera, isolate)
            viewport.frame_nodes(panel, isolate)
        except Exception:
            try:
                if panel:
                    viewport.delete_model_panel(panel)
            finally:
                with self._service("undo").suspended_undo():
                    if cmds.objExists(private_camera):
                        cmds.delete(private_camera)
            raise
        self._viewport_cameras[panel] = private_camera
        return panel

    @action()
    def viewport_container(self, panel):
        return self._service("viewport").panel_container(panel)

    @action()
    def frame_viewport(self, panel, nodes):
        return self._service("viewport").frame_nodes(panel, nodes)

    @action("Building demo scene…")
    def create_demo_scene(self):
        """Build the demo scene and add its source and destination models."""
        for character in list(self.session.characters):
            self.remove_model(character.character_id)
        for clip in list(self.session.clips):
            self.remove_clip(clip.clip_id)
        demo_module = self._service("demo")
        demo = demo_module.build_demo_scene(new_scene=True)
        self.add_model_from_scene(demo.source_root)
        self.add_model_from_scene(demo.destination_mesh or demo.destination_root)
        self.session.status(
            "Demo models ready. Start the proposed process below.", "success")
        return demo

    @action()
    def delete_viewport(self, panel):
        self._service("viewport").delete_model_panel(panel)
        camera = self._viewport_cameras.get(panel)
        if camera:
            with self._service("undo").suspended_undo():
                cmds = self._cmds()
                if cmds.objExists(camera):
                    cmds.delete(camera)
            self._viewport_cameras.pop(panel, None)

    @action()
    def shutdown(self):
        # View widgets normally release these first; also cover partial embeds.
        self.cancel_rig_fit()
        for panel in list(self._viewport_cameras):
            self.delete_viewport(panel)
        if self._previews:
            self.pause()
        for clip_id in list(self._previews):
            self.stop_preview(clip_id)
