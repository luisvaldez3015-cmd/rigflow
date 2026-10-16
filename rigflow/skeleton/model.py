"""Skeleton data model.

A :class:`Skeleton` is an immutable-ish snapshot of a joint hierarchy: names,
parent/child links and rest-pose world positions. It is built from a Maya
scene by :mod:`rigflow.scene.skeleton_reader`, or directly in tests, and is
consumed by the naming/topology analysers and the mapping logic. It never
touches Maya itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Tuple

from rigflow.utils import math3d
from rigflow.utils.strings import short_name


@dataclass
class JointInfo:
    """One joint (or transform acting as a joint) of a skeleton.

    Attributes:
        name: Unique identifier as used in the scene (full path or unique name).
        parent: ``name`` of the parent joint, or ``None`` for a root.
        world_position: Rest/bind pose world position (scene linear units).
        animated: Whether the node has animation curves connected.
        node_type: Maya node type (``"joint"`` or ``"transform"``).
        world_orient: Optional rest-pose world rotation as a 3x3 matrix
            flattened row-major; filled by the Maya reader when available.
    """

    name: str
    parent: Optional[str] = None
    world_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    animated: bool = False
    node_type: str = "joint"
    world_orient: Optional[Tuple[float, ...]] = None
    children: List[str] = field(default_factory=list)

    @property
    def short_name(self) -> str:
        return short_name(self.name)

    def to_dict(self) -> dict:
        data = {
            "name": self.name,
            "parent": self.parent,
            "world_position": list(self.world_position),
            "animated": self.animated,
            "node_type": self.node_type,
        }
        if self.world_orient is not None:
            data["world_orient"] = list(self.world_orient)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "JointInfo":
        orient = data.get("world_orient")
        return cls(
            name=data["name"],
            parent=data.get("parent"),
            world_position=tuple(data.get("world_position", (0.0, 0.0, 0.0))),  # type: ignore[arg-type]
            animated=bool(data.get("animated", False)),
            node_type=data.get("node_type", "joint"),
            world_orient=tuple(orient) if orient is not None else None,
        )


class Skeleton:
    """A joint hierarchy with rest-pose positions.

    Args:
        joints: Joint descriptions. ``children`` lists are rebuilt from the
            ``parent`` links, so callers only need to fill ``parent``.
        name: Display name (e.g. file name or namespace).
        up_axis: Scene up axis, ``"y"`` or ``"z"``.
        linear_unit: Scene linear unit string (``"cm"``, ``"m"``...). Informational.
    """

    def __init__(
        self,
        joints: Iterable[JointInfo],
        name: str = "",
        up_axis: str = "y",
        linear_unit: str = "cm",
    ):
        self.name = name
        self.up_axis = up_axis.lower()
        self.linear_unit = linear_unit
        self._joints: Dict[str, JointInfo] = {}
        for joint in joints:
            if joint.name in self._joints:
                raise ValueError("Duplicate joint name: {}".format(joint.name))
            joint.children = []
            self._joints[joint.name] = joint
        for joint in self._joints.values():
            if joint.parent is not None:
                parent = self._joints.get(joint.parent)
                if parent is None:
                    # Parent outside the skeleton (e.g. a group): treat as root.
                    joint.parent = None
                else:
                    parent.children.append(joint.name)
        self._depth_cache: Dict[str, int] = {}
        self._size_cache: Dict[str, int] = {}

    # --- basic access -----------------------------------------------------------

    def __len__(self) -> int:
        return len(self._joints)

    def __iter__(self) -> Iterator[str]:
        return iter(self._joints)

    def __contains__(self, name: object) -> bool:
        return name in self._joints

    @property
    def joint_names(self) -> List[str]:
        return list(self._joints)

    def joint(self, name: str) -> JointInfo:
        return self._joints[name]

    def get(self, name: str) -> Optional[JointInfo]:
        return self._joints.get(name)

    @property
    def roots(self) -> List[str]:
        return [j.name for j in self._joints.values() if j.parent is None]

    def main_root(self) -> Optional[str]:
        """Root with the largest subtree (the character, not stray props)."""
        roots = self.roots
        if not roots:
            return None
        return max(roots, key=self.subtree_size)

    def parent(self, name: str) -> Optional[str]:
        return self._joints[name].parent

    def children(self, name: str) -> List[str]:
        return list(self._joints[name].children)

    def is_leaf(self, name: str) -> bool:
        return not self._joints[name].children

    def position(self, name: str) -> Tuple[float, float, float]:
        return self._joints[name].world_position

    # --- hierarchy queries ---------------------------------------------------------

    def ancestors(self, name: str) -> List[str]:
        """Ancestors from the immediate parent up to the root."""
        result = []
        current = self._joints[name].parent
        while current is not None:
            result.append(current)
            current = self._joints[current].parent
        return result

    def descendants(self, name: str) -> List[str]:
        """All descendants in depth-first order."""
        result: List[str] = []
        stack = list(reversed(self._joints[name].children))
        while stack:
            current = stack.pop()
            result.append(current)
            stack.extend(reversed(self._joints[current].children))
        return result

    def depth(self, name: str) -> int:
        if name not in self._depth_cache:
            self._depth_cache[name] = len(self.ancestors(name))
        return self._depth_cache[name]

    def subtree_size(self, name: str) -> int:
        """Number of joints in the subtree rooted at ``name`` (inclusive)."""
        if name not in self._size_cache:
            self._size_cache[name] = 1 + len(self.descendants(name))
        return self._size_cache[name]

    def is_ancestor(self, ancestor: str, name: str) -> bool:
        return ancestor in self.ancestors(name)

    def main_chain(
        self,
        start: str,
        choose: Optional[Callable[[List[str]], Optional[str]]] = None,
        stop: Optional[Callable[[str], bool]] = None,
    ) -> List[str]:
        """Walk from ``start`` following one child at a time.

        Args:
            start: First joint of the chain.
            choose: Picks the next child among the available ones. Defaults to
                the child with the largest subtree.
            stop: When it returns True for a joint, the chain ends there.
        """
        if choose is None:

            def choose(kids: List[str]) -> Optional[str]:
                return max(kids, key=self.subtree_size) if kids else None

        chain = [start]
        current = start
        while True:
            if stop is not None and stop(current):
                break
            kids = self._joints[current].children
            nxt = choose(list(kids)) if kids else None
            if nxt is None:
                break
            chain.append(nxt)
            current = nxt
        return chain

    # --- geometry ---------------------------------------------------------------------

    def bone_length(self, name: str) -> float:
        """Distance from ``name`` to its parent (0 for roots)."""
        parent = self._joints[name].parent
        if parent is None:
            return 0.0
        return math3d.distance(self.position(name), self.position(parent))

    def bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        positions = [j.world_position for j in self._joints.values()]
        if not positions:
            zero = (0.0, 0.0, 0.0)
            return zero, zero
        mins = tuple(min(p[i] for p in positions) for i in range(3))
        maxs = tuple(max(p[i] for p in positions) for i in range(3))
        return mins, maxs  # type: ignore[return-value]

    def height(self) -> float:
        """Extent of the skeleton along the up axis."""
        mins, maxs = self.bounds()
        idx = math3d.AXIS_INDEX[self.up_axis]
        return maxs[idx] - mins[idx]

    def up(self, name: str) -> float:
        """Coordinate of a joint along the up axis."""
        return math3d.component(self.position(name), self.up_axis)

    def lateral(self, name: str, lateral_axis: str = "x") -> float:
        """Coordinate of a joint along the lateral (left/right) axis."""
        return math3d.component(self.position(name), lateral_axis)

    # --- serialisation --------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "up_axis": self.up_axis,
            "linear_unit": self.linear_unit,
            "joints": [j.to_dict() for j in self._joints.values()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Skeleton":
        return cls(
            [JointInfo.from_dict(j) for j in data.get("joints", [])],
            name=data.get("name", ""),
            up_axis=data.get("up_axis", "y"),
            linear_unit=data.get("linear_unit", "cm"),
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Skeleton({!r}, {} joints, roots={})".format(self.name, len(self), self.roots)
