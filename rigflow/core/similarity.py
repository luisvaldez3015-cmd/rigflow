"""Scene-independent result of comparing two meshes at rest."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class MeshSimilarity:
    """Percentage of matching samples and regions needing manual polish."""

    score: float
    matches: bool
    differing: List[str] = field(default_factory=list)
