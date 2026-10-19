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
| `Character`, `MeshSlot`, `RigSlot`, `AnimSlot`, `model_label()` | `rigflow.core.character` | One *model* added in Setup and the three slots RigFlow detected on it. |
| `TransferPlan`, `PlanKind`, `derive_plan()` | `rigflow.core.plan` | What the Setup step proposes for the models (source, destination, steps). |
| `Session`, `ModelInfo`, `RigInfo`, `SessionEvent` | `rigflow.core.session` | Observable app state: models + plan, active destination, clips. |
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

## Contract: models, plan and rig transfer (Setup redesign, 2026-10-19)

The Setup step works with **models**, not with separate Mesh / Rig / Anim
inputs. The artist presses one **Add** action per model (file drop, Maya
selection or scene picker); RigFlow detects what it contains and fills the
three slots. With two models the plan decides the process (see
`rigflow/core/plan.py`, pure and unit tested):

| Model A | Model B | Plan | Steps |
|---------|---------|------|-------|
| animated (any) | has a rig | `ANIMATION` (A → B) | Setup → Match → Transfer |
| animated (any) | mesh only | `RIG_THEN_ANIMATION` | Setup → Rig → Match → Transfer |
| rig, no anim | mesh only | `RIG` | Setup → Rig |
| both animated | both rigged | `ANIMATION`, A is the source, **Swap** allowed | Setup → Match → Transfer |
| neither animated, both rigged | | `NOTHING` | Setup |

Animation that RigFlow itself transferred (`AnimSlot.transferred`) never makes
a model the preferred source, so after a transfer the destination stays the
destination for the next animation.

```python
# rigflow/core/character.py  (pure, done)
@dataclass class MeshSlot: meshes: List[str]; vertex_count: int; skinned: bool          # .valid, .describe()
@dataclass class RigSlot:  root: str; skeleton: Optional[Skeleton]; labeling; convention; warnings
                           # .joint_count, .valid, .required_roles_found, .complete, .describe()
@dataclass class AnimSlot: frame_range; fps; animated_joints: int; transferred: bool = False
                           # .frame_count, .range_label, .describe()
@dataclass class Character: name; character_id; source_path; namespace; mesh; rig; anim; notes
                           # .has_mesh/.has_rig/.has_anim/.has_authored_anim/.usable, .contents(), .summary()
def model_label(index) -> "Model A" | "Model B" ...

# rigflow/core/plan.py  (pure, done)
class PlanKind(str, Enum): EMPTY, NEED_SECOND, ANIMATION, RIG_THEN_ANIMATION, RIG, NOTHING
@dataclass class TransferPlan: kind; source_id; destination_id; title; message; issues; can_swap
                           # .ready, .steps (["Setup","Match","Transfer"] / ["Setup","Rig","Match","Transfer"] /
                           # ["Setup","Rig"] / ["Setup"]), .first_step ("match"|"rig"|None),
                           # .action_label ("Start: Match ›"|"Start: Rig ›"), .transfers_animation
def derive_plan(characters, preferred_source_id=None) -> TransferPlan   # only the first two models take part

# rigflow/core/session.py  (done)
Session.characters: List[Character]; Session.plan: TransferPlan; Session.preferred_source_id
Session.add_character(c) / remove_character(id) / replace_character(id, c) / character_updated(id)
Session.get_character(id) / label_for(id) / set_preferred_source(id) / swap_direction() / recompute_plan()
Session.source / Session.destination  (Characters of the current plan, or None)
SessionEvent.CHARACTERS_CHANGED (payload: list) is always followed by SessionEvent.PLAN_CHANGED (payload: plan)
# model / rig / clips stay: they describe the ACTIVE transfer (destination model + rig, source clip),
# and are filled by Controller.start_plan() from the plan's destination and source.
```

```python
# rigflow/scene/characters.py  (Maya) — detect what one model brings
@dataclass
class CharacterScan:
    name: str
    meshes: List[MeshInfo]                 # non-intermediate polygon meshes (inspector.MeshInfo)
    skeleton: Optional[SkeletonInfo]       # the MAIN skeleton or None (inspector.SkeletonInfo)
    other_roots: List[str]                 # skeleton roots in scope that were not chosen
    frame_range: Optional[Tuple[float, float]]   # keys on the main skeleton's joints only (animation_io.animation_range)
    fps: float
    warnings: List[str]
    # has_mesh, has_rig, has_anim (frame_range is not None and skeleton.animated_joints > 0)

def scan_nodes(nodes: Optional[Sequence[str]], name: str) -> CharacterScan
    # nodes=None → whole scene; otherwise these nodes and their descendants (inspector._scene_nodes).
    # Main skeleton: if a skinned mesh is in scope, the root reached through its influences
    # (inspector.skeleton_root_for_mesh) wins; otherwise the root with the most joints.
    # Selecting ONLY a skinned mesh must still yield its skeleton (follow the influences out of
    # scope, add a warning). Selecting ONLY a root joint must still yield the meshes skinned to
    # it (meshes_for_skeleton). RigFlow helper nodes are never included (inspector._is_helper).
def meshes_for_skeleton(root: str) -> List[MeshInfo]
    # Scene meshes whose skinCluster influences include a joint under ``root``.
def scan_import(result: ImportResult) -> CharacterScan   # scan_nodes(result.new_nodes, <file stem>)

# rigflow/scene/importer.py — add OBJ
ImportResult.kind: "fbx" | "maya" | "obj"
import_file() accepts ".obj": load the "objExport" plugin if needed, cmds.file(path, i=True, type="OBJ",
    options="mo=1", namespace=ns, returnNewNodes=True, ...). Meshes only (no joints) is valid content.

# rigflow/rigging/transfer.py  (Maya) — copy a skeleton onto a mesh-only model
@dataclass
class RigFitResult:
    root: str                      # new root joint (unique name / DAG path)
    joints: List[str]              # new joints, same order as source_joints
    source_joints: List[str]       # the joints they were copied from
    scale: float                   # uniform factor applied to the copied skeleton
    offset: Tuple[float, float, float]
    skin_clusters: List[str]       # empty until bind_skeleton()
    warnings: List[str]

def fit_skeleton(source_root: str, meshes: Sequence[str], namespace: Optional[str] = None,
                 stance_time: Optional[float] = None) -> RigFitResult
    # One undo chunk "RigFlow: fit rig".
    # 1. Inside rest_pose(<source joints>, stance_time) duplicate the source hierarchy, joints only:
    #    delete non-joint descendants of the duplicate; the duplicate must carry NO animation curves
    #    (duplicate without input connections, then cut any keys that slipped through); parent it to the world.
    # 2. Rename: strip the source namespace; place the new joints in ``namespace`` when given (create it)
    #    or in the root namespace; let Maya uniquify clashes. Record the final names.
    # 3. Fit: exactWorldBoundingBox(meshes) vs the bounding box of the new joints' world positions.
    #    scale = mesh height / joint height along the scene up axis. Multiply every new joint's local
    #    translate (root included) by scale and scale the joint radius. Then move the root so the joints'
    #    lowest point sits on the mesh's lowest point and the joint bbox centre matches the mesh centre
    #    on the other two axes. Orientations are untouched (uniform scaling keeps them valid).
    # Errors (SceneError + hint): no meshes, a mesh already skinned, zero mesh or joint height.
def bind_skeleton(fit: RigFitResult, meshes: Sequence[str], max_influences: int = 4) -> RigFitResult
    # One undo chunk "RigFlow: bind rig". Per mesh: cmds.skinCluster(fit.joints, mesh, toSelectedBones=True,
    # bindMethod=0, normalizeWeights=1, maximumInfluences=max_influences, obeyMaxInfluences=True,
    # dropoffRate=4.0, name="rigflow_skin#"). Fills fit.skin_clusters and returns fit.
def remove_fit(fit: RigFitResult) -> None
    # Delete the new joints (skinClusters go with them); tolerate repeated removal; one undo chunk.
```

```python
# rigflow/ui/controller.py — ControllerBase additions (FakeController implements all of them)
def add_model_from_file(self, path) -> Optional[Character]        # import_file + scan_import → Character (keeps ImportResult for removal)
def add_model_from_selection(self) -> Optional[Character]         # scan_nodes(inspector.selection(), <first node short name>)
def add_model_from_scene(self, node: str) -> Optional[Character]  # scan_nodes([node], node short name); node from list_scene_candidates()
def list_scene_candidates(self) -> List[str]                      # skeleton roots + mesh transforms not owned by a model, no RigFlow helpers
def remove_model(self, character_id) -> Optional[Character]       # stops previews, removes clips, owned import nodes, resets session.model/rig
def replace_model_from_file(self, character_id, path) -> Optional[Character]   # load first, then remove the old one (same position)
def swap_direction(self) -> TransferPlan
def start_plan(self) -> Optional[dict]
    # Publishes session.model (ModelInfo) and session.rig (RigInfo) from the plan's destination.
    # ANIMATION: clip for the source's rig root (reuse the clip already created for this source), auto_map,
    #            set active → {"step": "match", "clip_id": ...}
    # RIG / RIG_THEN_ANIMATION: fit_rig() → {"step": "rig"}
def fit_rig(self) -> Optional[RigFitResult]        # fit_skeleton(source.rig.root, destination.mesh.meshes, namespace=destination.namespace)
def refit_rig(self) -> Optional[RigFitResult]      # remove_fit + fit_skeleton
def cancel_rig_fit(self) -> bool                   # remove_fit; the plan is unchanged
def rig_fit(self) -> Optional[RigFitResult]        # current fit or None
def rig_viewport_nodes(self) -> List[str]          # destination meshes + fitted root
def bind_rig(self) -> Optional[dict]
    # bind_skeleton; destination.rig = RigSlot(read_skeleton_rest(fit.root), labelled); destination.mesh.skinned = True;
    # session.character_updated → plan becomes ANIMATION (or NEED/NOTHING for a RIG plan);
    # if plan.transfers_animation → same as start_plan() → {"step": "match", "clip_id": ...} else {"step": "setup"}
# bake(): afterwards destination.anim = AnimSlot(frame_range, fps, len(baked_joints), transferred=True); character_updated.
# Character ↔ clip: Controller keeps {character_id: clip_id} for sources; remove_model removes that clip.
```

UI (`rigflow/ui`):

- `setup_view.py`: `add_tile` (big, shown when there are no models) inside `empty_area`
  ("Add a model", drop accepts .ma/.mb/.fbx/.obj); `models_row` with one `ModelCard`
  per model (`model_cards`); `small_add_tile` + "Add the second model" when exactly one model;
  `plan_banner` (`PlanBanner`) when two or more. No Validate button: the banner's `start_button`
  (primary, text = `plan.action_label`) calls `MainWindow.start_plan()`.
- `widgets/model_card.py`: `ModelCard` with `title_label` ("Model A"), `name_label`, `slots`
  dict {"Mesh","Rig","Anim"} → tiles with `badge` ("Detected"/"None") and `detail`,
  `replace_button`, `remove_button`; signals `replace_requested(str)`, `remove_requested(str)`,
  `file_dropped(str, str)`; `set_character(character, label)`.
- `widgets/plan_banner.py`: `PlanBanner` with `title_label`, `message_label`, `issues_label`,
  `swap_button`, `start_button`; `set_plan(plan)`.
- `rig_view.py`: `RigView(controller)` page: `title`, `viewport` (ViewportPanel isolating
  `controller.rig_viewport_nodes()`), `info_label` (scale, joints, "move joints in Maya if needed,
  then Bind"), `back_button` (cancels the fit), `refit_button`, `bind_button` (primary "Bind skin ›");
  signals `back_requested()`, `bound(dict)`; `set_fit(fit)`, `activate()`, `deactivate()`, `dispose()`.
- `widgets/step_indicator.py`: `set_steps(names)` (dynamic, from `plan.steps`) + `set_state(...)`.
- `main_window.py`: pages setup / rig / match / transfer. `start_plan()`, `open_rig()`,
  `open_match(clip_id)`, `open_transfer(clip_id)`, `show_setup()`, `new_animation()` (back to
  Setup and replace the source model from a file), `validate_active()` kept for scripts.
  `add_menu`: "From file…", "Use Maya selection", "From scene…" (picker over `list_scene_candidates()`).
- Match viewport titles come from the session labels ("Model A · <name>"), not hard-coded "Mesh A/B".

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
