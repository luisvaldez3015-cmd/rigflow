"""Import source files into isolated, removable namespaces."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from maya import cmds, mel

from rigflow.core import config
from rigflow.core.errors import ImportError_
from rigflow.core.logging import get_logger
from rigflow.scene.inspector import SceneReport, inspect_scene
from rigflow.scene.undo import undo_chunk

log = get_logger(__name__)


@dataclass
class ImportResult:
    """Imported file identity, owned nodes and scoped inspection report."""

    path: str
    kind: str
    namespace: str
    new_nodes: List[str]
    report: SceneReport


def _namespace(path: str, requested: Optional[str]) -> str:
    base = requested if requested is not None else (
        config.SOURCE_NAMESPACE_PREFIX + "_" + os.path.splitext(os.path.basename(path))[0])
    base = re.sub(r"[^A-Za-z0-9_]", "_", base.strip(":")) or config.SOURCE_NAMESPACE_PREFIX
    if base[0].isdigit():
        base = "_" + base
    candidate, index = base, 1
    while cmds.namespace(exists=":" + candidate):
        candidate = "{}_{}".format(base, index)
        index += 1
    return candidate


def _cleanup(nodes: Sequence[str], namespace: str) -> None:
    """Delete only owned nodes, then remove their namespace if it still exists."""
    existing = [n for n in nodes if cmds.objExists(n)]
    if existing:
        cmds.delete(existing)
    if cmds.namespace(exists=":" + namespace):
        cmds.namespace(removeNamespace=":" + namespace, deleteNamespaceContent=True)


def import_file(path: str, namespace: Optional[str] = None) -> ImportResult:
    """Import FBX, Maya ASCII or Maya Binary; reject and clean unusable content."""
    path = os.path.abspath(os.fspath(path))
    extension = os.path.splitext(path)[1].lower()
    if not os.path.isfile(path):
        raise ImportError_("File does not exist: {}".format(path),
                           hint="Choose an existing FBX, .ma or .mb file.")
    if extension not in (".fbx", ".ma", ".mb"):
        raise ImportError_("Unsupported file extension: {}".format(extension),
                           hint="Export the source as FBX, Maya ASCII (.ma) or Maya Binary (.mb).")
    ns = _namespace(path, namespace)
    kind = "fbx" if extension == ".fbx" else "maya"
    with undo_chunk("RigFlow: import source"):
        previous_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        before = set(cmds.ls(long=True) or [])
        try:
            # Absolute names avoid nesting under the user's current namespace.
            cmds.namespace(setNamespace=":")
            if kind == "fbx" and not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
                cmds.loadPlugin("fbxmaya", quiet=True)
            # Plugin loading can create persistent plugin infrastructure, not import content.
            before = set(cmds.ls(long=True) or [])
            file_type = {".fbx": "FBX", ".ma": "mayaAscii", ".mb": "mayaBinary"}[extension]
            try:
                imported = cmds.file(path, i=True, type=file_type, namespace=ns,
                                     returnNewNodes=True, ignoreVersion=True,
                                     mergeNamespacesOnClash=False,
                                     options="fbx" if kind == "fbx" else "v=0;") or []
            except RuntimeError:
                if kind != "fbx":
                    raise
                log.warning("FBX file translator failed; retrying with FBXImport")
                _cleanup(sorted(set(cmds.ls(long=True) or []) - before), ns)
                cmds.namespace(add=ns)
                cmds.namespace(setNamespace=":" + ns)
                escaped = path.replace("\\", "/").replace('"', '\\"')
                mel.eval('FBXImportMode -v add; FBXImport -f "{}"'.format(escaped))
                imported = sorted(set(cmds.ls(long=True) or []) - before)
            # Use full paths for reliable ownership when leaf names are duplicated.
            new_nodes = sorted(set(cmds.ls(imported, long=True) or []) |
                               (set(cmds.ls(long=True) or []) - before))
            report = inspect_scene(new_nodes)
            if not report.has_skeleton and not report.has_mesh:
                raise ImportError_("File imported but contained no joints or meshes",
                                   hint="Export a skeleton or polygon mesh; cameras and lights are not usable content.")
            log.info("Imported %s into %s (%d nodes)", path, ns, len(new_nodes))
            return ImportResult(path, kind, ns, new_nodes, report)
        except Exception as exc:
            _cleanup(sorted(set(cmds.ls(long=True) or []) - before), ns)
            if isinstance(exc, ImportError_):
                raise
            raise ImportError_("Could not import {}: {}".format(path, exc),
                               hint="Check the file in Maya and verify its format/plugin is available.") from exc
        finally:
            cmds.namespace(setNamespace=previous_namespace)


def remove_import(result: ImportResult) -> None:
    """Remove imported nodes and namespace, tolerating repeated removal."""
    with undo_chunk("RigFlow: remove source"):
        _cleanup(result.new_nodes, result.namespace)
