"""Rest-pose surface comparison shared with rig weight transfer."""
from contextlib import contextmanager
from dataclasses import dataclass

from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma

from rigflow.core.config import MESH_SIMILARITY_THRESHOLD, MESH_SIMILARITY_TOLERANCE
from rigflow.core.errors import SceneError
from rigflow.core.similarity import MeshSimilarity
from rigflow.scene.animation_io import up_axis
from rigflow.scene.inspector import find_meshes
from rigflow.scene.rest_pose import rest_pose
from rigflow.scene.undo import suspended_undo


def dag_path(node):
    selection = om.MSelectionList()
    selection.add(node)
    return selection.getDagPath(0)


def skin_function(cluster):
    selection = om.MSelectionList()
    selection.add(cluster)
    return oma.MFnSkinCluster(selection.getDependNode(0))


def vertex_component(count):
    component = om.MFnSingleIndexedComponent()
    obj = component.create(om.MFn.kMeshVertComponent)
    component.addElements(range(count))
    return obj


@dataclass
class Surface:
    info: object
    points: object
    counts: object
    indices: object
    data: object
    fn: object
    triangles: object


@dataclass
class Normalization:
    origin: tuple
    height: float

    def apply(self, point):
        return om.MPoint(*((point[i] - self.origin[i]) / self.height for i in range(3)))


def surfaces(meshes):
    """Snapshot visible shapes into detached, normalised API mesh data."""
    found = find_meshes(meshes)
    if not found:
        raise SceneError("No visible mesh to compare", hint="Choose polygon meshes, excluding intermediate shapes.")
    points = [om.MFnMesh(dag_path(mesh.shape)).getPoints(om.MSpace.kWorld) for mesh in found]
    low = [min(p[i] for group in points for p in group) for i in range(3)]
    high = [max(p[i] for group in points for p in group) for i in range(3)]
    axis = "xyz".index(up_axis())
    height = high[axis] - low[axis]
    if height < 1e-10:
        raise SceneError("Mesh height is zero", hint="Choose a mesh with nonzero height along the scene up axis.")
    origin = tuple(low[i] if i == axis else (low[i] + high[i]) / 2 for i in range(3))
    normalization = Normalization(origin, height)
    result = []
    for info, group in zip(found, points):
        counts, indices = om.MFnMesh(dag_path(info.shape)).getVertices()
        normal = om.MPointArray([normalization.apply(p) for p in group])
        data = om.MFnMeshData().create()
        fn = om.MFnMesh()
        fn.create(normal, counts, indices, parent=data)
        result.append(Surface(info, normal, counts, indices, data, fn, fn.getTriangles()))
    return result, normalization


@contextmanager
def meshes_at_rest(*mesh_groups):
    """Restore every influencing joint without changing the artist's undo history."""
    influences = list(dict.fromkeys(j for group in mesh_groups for m in find_meshes(group)
                                    for j in m.influences))
    with suspended_undo():
        with rest_pose(influences):
            yield


def same_topology(a, b):
    """Vertex index correspondence requires identical polygon connectivity."""
    return (len(a.points) == len(b.points) and list(a.counts) == list(b.counts)
            and list(a.indices) == list(b.indices))


def _samples(group, limit=2000):
    total = sum(len(s.points) for s in group)
    stride = max(1.0, total / float(limit))
    offset, next_index = 0, 0.0
    for surface in group:
        while int(next_index) < offset + len(surface.points):
            yield surface, int(next_index) - offset
            next_index += stride
        offset += len(surface.points)


def _distance(point, group):
    return min((s.fn.getClosestPoint(point, om.MSpace.kObject)[0] - point).length() for s in group)


def compare_meshes(source_meshes, destination_meshes, source_root=None):
    """Symmetric fraction of samples within 3% height, plus poor influence regions."""
    with meshes_at_rest(source_meshes, destination_meshes):
        source, _ = surfaces(source_meshes)
        target, _ = surfaces(destination_meshes)
        direct = len(source) == len(target) and all(same_topology(a, b) for a, b in zip(source, target))
        values, region_values = [], {}
        for group, other in ((source, target), (target, source)):
            samples = []
            for surface, index in _samples(group):
                if direct:
                    paired = other[group.index(surface)]
                    distance = (surface.points[index] - paired.points[index]).length()
                else:
                    distance = _distance(surface.points[index], other)
                hit = float(distance <= MESH_SIMILARITY_TOLERANCE)
                samples.append(hit)
                if group is source:
                    region_values.setdefault(surface.info.shape, []).append((index, hit))
            values.append(sum(samples) / len(samples))
        score = 100.0 * sum(values) / 2
        regions = {}
        for surface in source:
            if not surface.info.skin_cluster:
                continue
            skin = skin_function(surface.info.skin_cluster)
            weights, count = skin.getWeights(dag_path(surface.info.shape), vertex_component(len(surface.points)))
            joints = [p.fullPathName() for p in skin.influenceObjects()]
            for index, hit in region_values[surface.info.shape]:
                dominant = max(range(count), key=lambda j: weights[index * count + j])
                regions.setdefault(joints[dominant], []).append(hit)
        roles = {}
        if source_root:
            from rigflow.mapping.matcher import label_skeleton
            from rigflow.scene.skeleton_reader import read_skeleton
            labeling = label_skeleton(read_skeleton(source_root))
            roles = {dag_path(j).fullPathName(): labeling.role_of(j) for j in labeling.labels}
        differing = []
        for joint, hits in regions.items():
            fraction = sum(hits) / len(hits)
            if fraction < 0.65 and fraction < score / 100 - 0.20:
                name = roles.get(joint) or joint.rsplit("|", 1)[-1].rsplit(":", 1)[-1]
                if name not in differing:
                    differing.append(name)
        return MeshSimilarity(score, score >= MESH_SIMILARITY_THRESHOLD, sorted(differing))
