# Architecture and module contracts

This document is the agreement between the RigFlow modules. Anyone adding a
module (human or agent) codes against these contracts; changes to them go
through the Technical Director (project owner) first.

## Layering

```
          ┌─────────────────────────── rigflow.ui ───────────────────────────┐
          │  Qt widgets. Never import maya.cmds. Talk to Controller/Session.  │
          └───────────────────────────────┬──────────────────────────────────┘
                                          │
          ┌───────────────────────────────▼──────────────────────────────────┐
          │ rigflow.ui.controller  (Maya)  orchestrates services, fills Session│
          └───────┬───────────────────────┬───────────────────────┬──────────┘
                  │                       │                       │
   rigflow.scene (Maya)       rigflow.retargeting (Maya)   rigflow.animation (Maya+pure)
   inspect / import / read    HIK + matrix backends, bake  clip model, clip library
                  │                       │                       │
          ┌───────▼───────────────────────▼───────────────────────▼──────────┐
          │ PURE: rigflow.core (config, errors, logging, session, compat)      │
          │       rigflow.skeleton (model, roles, naming, topology)            │
          │       rigflow.mapping (model, matcher, validation, presets)        │
          │       rigflow.utils                                                │
          └────────────────────────────────────────────────────────────────────┘
```

Rules:

- Pure packages never import `maya`. They are covered by `tests/unit`.
- Maya packages import `maya.cmds` / `maya.mel` / `maya.api.OpenMaya` at module
  level and are covered by `tests/integration` (run with `mayapy`).
- `rigflow.ui` never imports `maya.cmds` directly. Viewport embedding goes
  through `rigflow.scene.viewport`.
- Every scene modification runs inside `rigflow.scene.undo.undo_chunk`.
- Errors raised to the user are `rigflow.core.errors.RigFlowError` subclasses
  with a `hint`.

## Shared data types (pure, already implemented)

| Type | Module | Purpose |
|------|--------|---------|
| `Skeleton`, `JointInfo` | `rigflow.skeleton.model` | Joint graph with rest-pose world positions. |
| roles (`"Hips"`, `"LeftArm"`...) | `rigflow.skeleton.roles` | Canonical vocabulary = HumanIK slot names. |
| `SkeletonLabeling`, `JointLabel` | `rigflow.mapping.model` | Role per joint with confidence/evidence. |
| `JointMapping`, `JointMatch`, `MatchStatus` | `rigflow.mapping.model` | Role → (source joint, destination joint) table with green/yellow/red. |
| `ValidationReport` | `rigflow.mapping.validation` | Errors block transfer; warnings are shown. |
| `AnimationClip`, `ClipStatus` | `rigflow.animation.clip` | One source animation and its state. |
| `Session`, `ModelInfo`, `RigInfo`, `SessionEvent` | `rigflow.core.session` | Observable app state. |
| sample specs (`mixamo_spec`, `custom_spec`...) | `rigflow.skeleton.samples` | Canonical demo characters shared by tests, UI preview and `rigflow.scene.demo`. |

Entry points already available: `rigflow.mapping.auto_map(source_skeleton,
destination_skeleton, previous=None)` → `(JointMapping, SkeletonLabeling,
SkeletonLabeling)`; `rigflow.mapping.validate_mapping(mapping, src, dst)`.

## Contract: `rigflow.scene` (Maya)

```python
# rigflow/scene/inspector.py
@dataclass
class MeshInfo:
    transform: str; shape: str; vertex_count: int
    skinned: bool; skin_cluster: Optional[str]; influences: List[str]

@dataclass
class SkeletonInfo:
    root: str; joints: List[str]; animated_joints: int
    has_bind_pose: bool; namespace: str
    # joint_count property = len(joints)

@dataclass
class SceneReport:
    meshes: List[MeshInfo]; skeletons: List[SkeletonInfo]; controls: List[str]
    frame_range: Optional[Tuple[float, float]]   # keys found on the inspected nodes
    fps: float; time_unit: str; linear_unit: str; up_axis: str
    warnings: List[str]
    # helpers: has_animation, has_mesh, has_skeleton, describe() -> str for the UI

def inspect_scene(nodes: Optional[Sequence[str]] = None) -> SceneReport
    # None → whole scene. Otherwise only these nodes and their descendants.
def find_skeleton_roots(nodes: Optional[Sequence[str]] = None) -> List[str]
    # Top-most joints (no joint ancestor). Ignore joints under RigFlow's own HIK nodes.
def find_meshes(nodes: Optional[Sequence[str]] = None) -> List[MeshInfo]
def is_control(node: str) -> bool            # nurbsCurve/locator shapes or ".ctrl"-like names
def skeleton_root_for_mesh(mesh: MeshInfo) -> Optional[str]   # via skinCluster influences
def selection() -> List[str]

# rigflow/scene/skeleton_reader.py
def read_skeleton(root: str, name: Optional[str] = None) -> Skeleton
    # All joints under root (type joint). world_position from xform at the CURRENT pose,
    # animated flag from animation curves, world_orient from the world matrix (3x3).
    # up_axis / linear_unit from the scene.
def read_skeleton_rest(root: str, name=None, stance_time: Optional[float] = None) -> Skeleton
    # Same, but inside rigflow.scene.rest_pose.rest_pose(joints, stance_time).

# rigflow/scene/importer.py
@dataclass
class ImportResult:
    path: str; kind: str                 # "fbx" | "maya"
    namespace: str; new_nodes: List[str]
    report: SceneReport                  # inspection restricted to new_nodes
def import_file(path: str, namespace: Optional[str] = None) -> ImportResult
    # Unique namespace: config.SOURCE_NAMESPACE_PREFIX + "_" + sanitized basename (+ _N).
    # FBX through the fbxmaya plugin (load if needed); .ma/.mb through cmds.file(i=True).
    # Raises ImportError_ with a hint when nothing usable (no joints and no meshes) came in.
def remove_import(result: ImportResult) -> None   # delete nodes, remove namespace

# rigflow/scene/animation_io.py
def animation_range(nodes: Sequence[str]) -> Optional[Tuple[float, float]]
def has_animation(node: str) -> bool
def scene_fps() -> float; def time_unit() -> str; def linear_unit() -> str; def up_axis() -> str
def set_playback_range(start: float, end: float) -> None

# rigflow/scene/undo.py       undo_chunk(name), undoable(name), suspended_undo()   (done)
# rigflow/scene/rest_pose.py  rest_pose(joints, stance_time=None), bind_pose_node()  (done)

# rigflow/scene/viewport.py
def create_model_panel(parent_qt_layout_name: str, camera: str = "persp", isolate: Sequence[str] = ()) -> str
    # Creates a cmds.modelPanel inside a paneLayout parented to a *Qt layout* found
    # by object name (cmds.setParent accepts QLayout names, not QWidget names), with
    # optional isolate-select of the given nodes. Returns the panel name.
def panel_container(panel: str) -> Optional[str]   # the paneLayout to wrap and embed
def delete_model_panel(panel: str) -> None
def frame_nodes(panel: str, nodes: Sequence[str]) -> None

# rigflow/scene/demo.py
def build_demo_scene(animate=True, with_mesh=True, with_face=True, new_scene=False) -> DemoScene
    # Mixamo-style animated source + short custom destination with skinned proxy mesh
    # and a jaw/eyes facial setup. Shared by tests, Help → Create demo scene, trailer.
```

## Contract: `rigflow.retargeting` (Maya)

```python
# rigflow/retargeting/base.py
@dataclass
class RetargetRequest:
    mapping: JointMapping
    source_root: str
    destination_root: str
    frame_range: Tuple[float, float]
    bake_to_layer: bool = True
    layer_name: str = config.BAKE_LAYER_NAME
    sample_by: float = 1.0
    stance_time: Optional[float] = None       # frame used to capture the source rest pose
    transfer_root_motion: bool = True

@dataclass
class RetargetResult:
    backend: str
    baked_joints: List[str]
    layer: Optional[str]
    frame_range: Tuple[float, float]
    warnings: List[str]
    verification: Dict[str, float]   # e.g. "max_bone_length_error", "hips_travel", "elapsed_s"

class Retargeter:                     # abstract base
    name: str                          # "humanik" | "matrix"
    @classmethod
    def availability(cls) -> Tuple[bool, str]       # (available, reason)
    def prepare(self, request: RetargetRequest) -> None   # build live retarget (preview)
    @property
    def prepared(self) -> bool
    def bake(self) -> RetargetResult                # bake keys, then cleanup live nodes
    def cleanup(self) -> None                        # cancel preview, remove own nodes only

# rigflow/retargeting/hik.py     class HumanIKRetargeter(Retargeter)  — see humanik-backend.md
# rigflow/retargeting/matrix.py  class MatrixRetargeter(Retargeter)   — fallback
# rigflow/retargeting/verify.py  sample_world_positions(joints, frames) -> Dict[joint, List[Vec3]]
#                                bone_length_error(root, frames) -> float
# rigflow/retargeting/__init__.py
def available_backends() -> List[Tuple[str, bool, str]]
def get_retargeter(preferred: Optional[str] = None) -> Retargeter   # HIK if available else matrix
```

Both backends must: run inside an undo chunk; use `rest_pose` for the source
stance; never write keys outside `request.frame_range`; only touch destination
joints present in `mapping.complete_pairs()`; delete only nodes they created.

## Contract: `rigflow.ui`

- `rigflow/ui/qt.py` exposes `QtCore, QtGui, QtWidgets, Signal, Slot, wrapInstance, QT_BINDING`.
- `rigflow/ui/theme.py` holds the palette, spacing scale and the stylesheet.
- `rigflow/ui/controller.py` is the only UI module importing scene/retargeting.
- `rigflow/ui/launcher.py::show(dev_reload=False)` returns the single main window
  (object name `config.WINDOW_OBJECT_NAME`), raising it if already open.
- Views: `main_window.py` (Model / Rig / Animation sections), `matching_view.py`
  (source and destination panels, mapping table with statuses), `review_view.py`
  (playback controls, warnings, Back / Confirm).
- Every widget must be constructible off-screen (`QT_QPA_PLATFORM=offscreen`)
  with a fake controller for smoke tests.
