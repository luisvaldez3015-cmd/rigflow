"""HumanIK implementation of the verified standalone MEL pipeline."""

from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Tuple

from maya import cmds, mel

from rigflow.core.errors import RetargetError, UnsupportedError
from rigflow.core.logging import get_logger
from rigflow.scene.rest_pose import rest_pose
from rigflow.scene.undo import undo_chunk

from .base import Retargeter, RetargetRequest, RetargetResult, chunked, sample_frames, skeleton_joints
from .baker import bake_joints, create_override_layer, unique_layer_name
from .verify import sample_world_positions

log = get_logger(__name__)
_PLUGINS = ("mayaHIK", "mayaCharacterization", "retargeterNodes")
_SCRIPTS = ("hikGlobalUtils.mel", "hikDefinitionOperations.mel", "hikInputSourceUtils.mel")


class HumanIKRetargeter(Retargeter):
    """Live HIK preview followed by a direct or non-destructive layer bake."""

    name = "humanik"

    @classmethod
    def availability(cls) -> Tuple[bool, str]:
        """Load the three plugins to verify availability even before registration."""
        try:
            with undo_chunk("RigFlow: check HumanIK plugins"):
                for plugin in _PLUGINS:
                    if not cmds.pluginInfo(plugin, query=True, loaded=True):
                        cmds.loadPlugin(plugin)
        except RuntimeError as exc:
            return False, "HumanIK unavailable: " + str(exc)
        return True, "HumanIK skeleton retargeting with live preview"

    def _characterize(self, name: str, slots: dict) -> str:
        character = mel.eval("hikCreateCharacter({})".format(json.dumps(unique_layer_name(name))))
        mel.eval("hikSetCurrentCharacter({})".format(json.dumps(character)))
        for role, joint in slots.items():
            slot = int(mel.eval("hikGetNodeIdFromName({})".format(json.dumps(role))))
            if slot < 0:
                raise RetargetError("Unknown HIK slot: " + role, hint="use HumanIK role names")
            mel.eval("setCharacterObject({},{},{},0)".format(
                json.dumps(joint), json.dumps(character), slot))
            assigned = mel.eval("hikGetSkNode({},{})".format(json.dumps(character), slot))
            if not assigned or cmds.ls(assigned, long=True) != cmds.ls(joint, long=True):
                raise RetargetError("HumanIK failed to assign " + role,
                                    hint="check that the joint is not assigned to another character")
        mel.eval("hikCharacterLock({},1,1)".format(json.dumps(character)))
        if not cmds.getAttr(character + ".InputCharacterizationLock"):
            raise RetargetError("HumanIK stance did not lock", hint="check the stance and mapping")
        return character

    @chunked("RigFlow: prepare {} preview")
    def prepare(self, request: RetargetRequest) -> None:
        """Characterize destination then source stance, and enable live preview."""
        self._begin(request)
        self._baked = False
        self._destination_channels = {}
        before = set(cmds.ls() or [])
        try:
            for plugin in _PLUGINS:
                if not cmds.pluginInfo(plugin, query=True, loaded=True):
                    cmds.loadPlugin(plugin)
            for script in _SCRIPTS:
                mel.eval('source "{}";'.format(script))
            pairs = request.mapping.complete_pairs()
            self._translation_joints = []
            for role, _, joint in pairs:
                translated = any(cmds.keyframe(joint, attribute=a, query=True, keyframeCount=True)
                                 for a in ("tx", "ty", "tz"))
                if (role == "Hips" and request.transfer_root_motion) or (role != "Hips" and translated):
                    self._translation_joints.append(joint)
                for attr in ("tx", "ty", "tz", "rx", "ry", "rz"):
                    plug = joint + "." + attr
                    self._destination_channels[plug] = (
                        cmds.getAttr(plug), cmds.listConnections(plug, source=True,
                                                               destination=False, plugs=True) or [])
            source_joints = skeleton_joints(request.source_root)
            destination_joints = skeleton_joints(request.destination_root)
            stance = request.stance_time if request.stance_time is not None else request.frame_range[0]
            animated = any(cmds.keyframe(j, query=True, keyframeCount=True)
                           for j in destination_joints)
            pose = rest_pose(destination_joints, stance) if animated else nullcontext("current-pose")
            with pose as method:
                destination = self._characterize("rigflow_dst_character",
                                                {r: d for r, _, d in pairs})
                self._warnings.append("Destination stance: " + method)
            with rest_pose(source_joints, stance) as method:
                source = self._characterize("rigflow_src_character", {r: s for r, s, _ in pairs})
                self._warnings.append("Source stance: " + method)
            cmds.optionVar(intValue=("hikRetargetUsingRig", 0))
            mel.eval("hikSetCharacterInput({},{})".format(json.dumps(destination), json.dumps(source)))
            # Keep the live preview on exactly the channels the bake transfers.
            # HIK emits small, time-varying non-root translation corrections;
            # leaving those live would make a rotation-only bake differ from
            # its preview on skeletons with different limb proportions.
            for _, _, joint in pairs:
                if joint not in self._translation_joints:
                    for attr in ("tx", "ty", "tz"):
                        self._restore_channel(joint + "." + attr)
            self._warnings.append("Preview and bake retain unanimated non-root translations")
            self._source_hips, self._destination_hips = next(
                (s, d) for r, s, d in pairs if r == "Hips")
            # Start and midpoint catch a jump whose endpoints have equal height.
            start, end = request.frame_range
            frames = (start, start + (end - start) * 0.5)
            positions = sample_world_positions([self._source_hips, self._destination_hips], frames)
            def moved(node: str) -> bool:
                a, b = positions[node]
                return sum((x - y) ** 2 for x, y in zip(a, b)) > 1e-10
            if request.transfer_root_motion and moved(self._source_hips) and not moved(self._destination_hips):
                raise RetargetError("HumanIK preview is static while source hips move",
                                    hint="check stance pose and mapping, or use the matrix backend")
            self._prepared = True
            log.info("HumanIK preview prepared for %d joints", len(pairs))
        except Exception as exc:
            self._record_nodes(before, live=True)
            self.cleanup()
            if isinstance(exc, (RetargetError, UnsupportedError)):
                raise
            raise RetargetError("HumanIK preparation failed: " + str(exc),
                                hint="check HumanIK plugins, mapping and rest pose") from exc
        else:
            self._record_nodes(before, live=True)

    @chunked("RigFlow: transfer animation ({})")
    def bake(self) -> RetargetResult:
        """Bake mapped rotations and eligible translations, then remove HIK."""
        request = self._require_prepared()
        before = set(cmds.ls() or [])
        layer = None
        previous = cmds.currentTime(query=True)
        try:
            pairs = request.mapping.complete_pairs()
            joints = [d for _, _, d in pairs]
            frames = sample_frames(request.frame_range, request.sample_by)
            preview = sample_world_positions(joints, frames)
            layer = create_override_layer(request.layer_name) if request.bake_to_layer else None
            bake_joints(joints, request.frame_range, request.sample_by, ("rx", "ry", "rz"), layer)
            bake_joints(self._translation_joints, request.frame_range, request.sample_by,
                        ("tx", "ty", "tz"), layer)
            self._delete_live()
            self._baked = True
            baked = sample_world_positions(joints, frames)
            error = max(abs(a - b) for joint in joints
                        for p, q in zip(preview[joint], baked[joint]) for a, b in zip(p, q))
            if error > 1e-3:
                raise RetargetError("Baked motion differs from preview by {:.6g} cm".format(error),
                                    hint="undo the bake and check destination animation layers")
            result = self._result(layer)
            result.verification["max_preview_position_error"] = error
            return result
        except Exception as exc:
            if isinstance(exc, RetargetError):
                raise
            raise RetargetError("HumanIK bake failed: " + str(exc),
                                hint="check writable destination channels and animation layers") from exc
        finally:
            self._record_nodes(before)
            cmds.currentTime(previous, edit=True)
            self.cleanup()

    def _restore_channel(self, plug: str) -> None:
        """Restore a saved input/value after removing a solver channel."""
        if cmds.getAttr(plug, lock=True):
            return
        value, sources = self._destination_channels[plug]
        for current in cmds.listConnections(plug, source=True, destination=False, plugs=True) or []:
            cmds.disconnectAttr(current, plug)
        if sources:
            cmds.connectAttr(sources[0], plug, force=True)
        else:
            cmds.setAttr(plug, value)

    def _delete_live(self) -> None:
        # HIK inserts pairBlends for previously keyed channels. Before deleting
        # these owned intermediaries, bypass them so an override layer's base
        # continues to receive the original animation (or original static value).
        for node in self._live_nodes:
            if not cmds.objExists(node) or cmds.nodeType(node) != "pairBlend":
                continue
            for kind in ("Translate", "Rotate"):
                compound = node + ".out" + kind
                targets = cmds.connectionInfo(compound, destinationFromSource=True) or []
                for target in targets:
                    cmds.disconnectAttr(compound, target)
                    for axis in "XYZ":
                        self._bypass_input(node + ".in" + kind + axis + "1", target + axis)
                for axis in "XYZ":
                    output = compound + axis
                    for target in cmds.connectionInfo(output, destinationFromSource=True) or []:
                        cmds.disconnectAttr(output, target)
                        self._bypass_input(node + ".in" + kind + axis + "1", target)
        super()._delete_live()

    @staticmethod
    def _bypass_input(source: str, destination: str) -> None:
        inputs = cmds.listConnections(source, source=True, destination=False, plugs=True) or []
        if inputs:
            cmds.connectAttr(inputs[0], destination, force=True)
        else:
            cmds.setAttr(destination, cmds.getAttr(source))

    def cleanup(self) -> None:
        """Remove the preview and restore original destination inputs on cancel."""
        try:
            with undo_chunk("RigFlow: restore destination"):
                self._delete_live()
                if not getattr(self, "_baked", True):
                    for plug in getattr(self, "_destination_channels", {}):
                        if cmds.objExists(plug):
                            self._restore_channel(plug)
                    self._destination_channels = {}
        finally:
            super().cleanup()
