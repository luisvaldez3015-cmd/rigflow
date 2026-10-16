"""Retargeting contract and shared validation/lifecycle support."""

from __future__ import annotations

import functools
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from maya import cmds

from rigflow.core import config
from rigflow.core.errors import RetargetError
from rigflow.core.logging import get_logger
from rigflow.mapping.model import JointMapping
from rigflow.scene.undo import undo_chunk
from rigflow.skeleton.roles import REQUIRED_ROLES

log = get_logger(__name__)


@dataclass
class RetargetRequest:
    """One transfer, expressed in the scene's current time and linear units."""

    mapping: JointMapping
    source_root: str
    destination_root: str
    frame_range: Tuple[float, float]
    bake_to_layer: bool = True
    layer_name: str = config.BAKE_LAYER_NAME
    sample_by: float = 1.0
    stance_time: Optional[float] = None
    transfer_root_motion: bool = True


@dataclass
class RetargetResult:
    """Baked scene objects and numeric verification (distances in cm)."""

    backend: str
    baked_joints: List[str]
    layer: Optional[str]
    frame_range: Tuple[float, float]
    warnings: List[str]
    verification: Dict[str, float]


def sample_frames(frame_range: Tuple[float, float], sample_by: float) -> List[float]:
    """Return the requested samples without ever extending the end time."""
    start, end = frame_range
    count = int(math.floor((end - start) / sample_by + 1e-9))
    return [min(end, start + i * sample_by) for i in range(count + 1)]


def skeleton_joints(root: str) -> List[str]:
    """Include all joints, including unmapped intermediary stance joints."""
    return ([root] if cmds.nodeType(root) == "joint" else []) + (
        cmds.listRelatives(root, allDescendents=True, type="joint", fullPath=True) or []
    )


def chunked(name: str) -> Callable:
    """Run a backend method inside one closed undo chunk.

    ``name`` may contain ``{}`` for the backend name. Each public operation
    (prepare, bake, cleanup) is its own undo step; chunks are never held open
    across user interaction. Callers that want *prepare + bake* to be a single
    undo step wrap both calls in an outer ``undo_chunk`` (nested chunks merge).
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            with undo_chunk(name.format(self.name)):
                return func(self, *args, **kwargs)

        return wrapper

    return decorator


class Retargeter(ABC):
    """Backend interface.

    ``prepare`` builds the (live) retarget, ``bake`` writes keys and removes
    the transient nodes, ``cleanup`` abandons a prepared preview. Every one of
    them is a self-contained undo step; nothing stays open in between.
    """

    name: str

    def __init__(self) -> None:
        self._request: Optional[RetargetRequest] = None
        self._prepared = False
        self._created_nodes: List[str] = []
        self._live_nodes: List[str] = []
        self._warnings: List[str] = []
        self._started = 0.0

    @classmethod
    @abstractmethod
    def availability(cls) -> Tuple[bool, str]:
        """Return whether this backend can run and a user-facing reason."""

    @abstractmethod
    def prepare(self, request: RetargetRequest) -> None:
        """Validate and prepare a transfer; HIK also provides live preview."""

    @property
    def prepared(self) -> bool:
        """Whether bake can currently be called."""
        return self._prepared

    @abstractmethod
    def bake(self) -> RetargetResult:
        """Bake the prepared request and remove transient solver nodes."""

    def _validate(self, request: RetargetRequest) -> None:
        pairs = request.mapping.complete_pairs()
        missing = sorted(set(REQUIRED_ROLES) - {role for role, _, _ in pairs})
        if missing:
            raise RetargetError("Missing required roles: " + ", ".join(missing),
                                hint="complete the mapping")
        for node in [request.source_root, request.destination_root] + [
            j for _, source, destination in pairs for j in (source, destination)
        ]:
            if not cmds.objExists(node):
                raise RetargetError("Joint/root does not exist: " + node,
                                    hint="refresh the skeletons and complete the mapping")
            if len(cmds.ls(node, long=True) or []) != 1:
                raise RetargetError("Joint/root name is ambiguous: " + node,
                                    hint="use full DAG paths in the mapping")
        for _, source, destination in pairs:
            if cmds.nodeType(source) != "joint" or cmds.nodeType(destination) != "joint":
                raise RetargetError("Mapping contains a non-joint", hint="map skeleton joints")
        try:
            start, end = request.frame_range
            valid = all(math.isfinite(v) for v in (start, end, request.sample_by))
            valid = valid and start <= end and request.sample_by > 0
            valid = valid and (request.stance_time is None or math.isfinite(request.stance_time))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise RetargetError("Invalid frame range or sample interval",
                                hint="use a finite ordered frame range and positive sample_by")
        sources = {cmds.ls(s, long=True)[0] for _, s, _ in pairs}
        destinations = [cmds.ls(d, long=True)[0] for _, _, d in pairs]
        if (sources.intersection(destinations) or len(set(destinations)) != len(destinations)
                or len(sources) != len(pairs)):
            raise RetargetError("Mapping overlaps or repeats destination joints",
                                hint="use distinct source and destination skeletons and unique pairs")

    def _begin(self, request: RetargetRequest) -> None:
        if self._prepared or self._live_nodes:
            self.cleanup()
        self._validate(request)
        self._request = request
        self._created_nodes = []
        self._live_nodes = []
        self._warnings = []
        skipped = [r for r, m in request.mapping.matches.items() if not m.transferable]
        if skipped:
            self._warnings.append("Skipped roles: " + ", ".join(sorted(skipped)))
        self._started = time.perf_counter()

    def _require_prepared(self) -> RetargetRequest:
        if not self.prepared or self._request is None:
            raise RetargetError("No prepared transfer", hint="prepare a mapping before baking")
        return self._request

    def _record_nodes(self, before: set, live: bool = False) -> None:
        """Record only nodes added by the immediately surrounding operation."""
        added = set(cmds.ls() or []) - before
        self._created_nodes.extend(sorted(added - set(self._created_nodes)))
        if live:
            self._live_nodes.extend(sorted(added - set(self._live_nodes)))

    def _delete_live(self) -> None:
        nodes = [n for n in self._live_nodes if cmds.objExists(n)]
        if nodes:
            cmds.delete(nodes)
        self._live_nodes = []

    def cleanup(self) -> None:
        """Cancel preview, deleting only owned transient nodes; keep baked data."""
        try:
            with undo_chunk("RigFlow: cleanup retarget"):
                self._delete_live()
        finally:
            self._prepared = False

    def _result(self, layer: Optional[str]) -> RetargetResult:
        from .verify import bone_length_error, travel

        request = self._require_prepared()
        joints = [d for _, _, d in request.mapping.complete_pairs()]
        hips = next(d for role, _, d in request.mapping.complete_pairs() if role == "Hips")
        frames = sample_frames(request.frame_range, request.sample_by)
        verification = {
            "max_bone_length_error": bone_length_error(joints, frames),
            "hips_travel": travel(hips, frames),
            "elapsed_s": time.perf_counter() - self._started,
        }
        log.info("%s bake: %s", self.name, verification)
        return RetargetResult(self.name, joints, layer, request.frame_range,
                              list(self._warnings), verification)
