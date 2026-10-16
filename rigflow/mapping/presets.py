"""Save and load joint mappings as JSON presets.

A preset stores role -> (source joint, destination joint) pairs plus manual
overrides and exclusions, so an artist can reuse a corrected mapping for the
next animation from the same pair of skeletons.
"""

from __future__ import annotations

import io
import json
import os

from rigflow.core.errors import MappingError
from rigflow.mapping.model import JointMapping

PRESET_EXTENSION = ".rigflow.json"


def save_mapping(mapping: JointMapping, path: str) -> str:
    """Write ``mapping`` to ``path`` (directories are created). Returns the path."""
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(mapping.to_dict(), handle, indent=2, sort_keys=False)
    return path


def load_mapping(path: str) -> JointMapping:
    """Read a mapping preset. Raises :class:`MappingError` on invalid files."""
    if not os.path.isfile(path):
        raise MappingError("Preset not found: {}".format(path))
    try:
        with io.open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except ValueError as exc:
        raise MappingError("Preset is not valid JSON: {}".format(path), hint=str(exc))
    if not isinstance(data, dict) or data.get("format") != "rigflow-mapping":
        raise MappingError("File is not a RigFlow mapping preset", hint=path)
    version = int(data.get("version", 0))
    if version > JointMapping.FORMAT_VERSION:
        raise MappingError(
            "Preset was written by a newer RigFlow (format {})".format(version),
            hint="Update RigFlow to open this preset",
        )
    return JointMapping.from_dict(data)
