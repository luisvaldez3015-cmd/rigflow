"""Central configuration and constants.

Every tunable number used by the matching and retargeting logic lives here
with a short explanation, so there are no unexplained magic numbers in the
algorithms themselves.
"""

from __future__ import annotations

# --- Identity -----------------------------------------------------------------

PROJECT_NAME = "RigFlow"
TOOL_TITLE = "RigFlow — Animation Transfer"
WINDOW_OBJECT_NAME = "rigflowMainWindow"
#: Planned public repository. Update when the repository is published.
REPO_URL = "https://github.com/luisvaldez3015-cmd/rigflow"
ISSUES_URL = REPO_URL + "/issues/new/choose"
#: Documentation entries exposed by the Help menu. Relative paths resolve
#: against the repository ``docs/`` folder (GitHub renders Markdown directly).
DOCS = {
    "User Guide": "docs/user/user-guide.md",
    "Installation Guide": "docs/user/installation.md",
    "Supported Formats and Compatibility": "docs/user/compatibility.md",
    "Skeleton Matching Guide": "docs/user/skeleton-matching.md",
    "Animation Transfer Guide": "docs/user/animation-transfer.md",
    "Troubleshooting": "docs/user/troubleshooting.md",
    "Developer Documentation": "docs/developer/README.md",
}

# --- Scene conventions ----------------------------------------------------------

#: Namespace prefix used when importing source animation files so that the
#: imported nodes never clash with the destination character.
SOURCE_NAMESPACE_PREFIX = "rigflow_src"
#: Name of the animation layer created when baking non-destructively.
BAKE_LAYER_NAME = "rigflow_transfer"

# --- Matching thresholds --------------------------------------------------------

#: Confidence at or above which a match is shown green (high confidence).
GREEN_THRESHOLD = 0.8
#: Confidence at or above which a match is shown yellow (needs review).
#: Below this value a match is treated as unreliable.
YELLOW_THRESHOLD = 0.5

#: Confidence assigned when naming and topology analyses agree on a role.
CONFIDENCE_AGREEMENT = 0.95
#: Confidence for a role supported only by an explicit, unambiguous name.
CONFIDENCE_NAME_ONLY_EXPLICIT = 0.8
#: Confidence for a role supported only by topology (nameless skeletons).
CONFIDENCE_TOPOLOGY_ONLY = 0.65
#: Confidence when the name is ambiguous and topology picks one alternative.
CONFIDENCE_TOPOLOGY_RESOLVES_AMBIGUITY = 0.9
#: Confidence when name and topology disagree and the name wins.
CONFIDENCE_CONFLICT_NAME_WINS = 0.5
#: Confidence when name and topology disagree and topology wins.
CONFIDENCE_CONFLICT_TOPOLOGY_WINS = 0.55
#: Confidence assigned to a manual override (the user validated it).
CONFIDENCE_MANUAL = 1.0

# --- Topology analysis ----------------------------------------------------------

#: A child branch counts as "significant" when its subtree has at least this
#: many joints. Filters out single end/tip joints when searching for the hips
#: and the chest.
SIGNIFICANT_BRANCH_MIN_JOINTS = 2
#: Maximum depth walked from the root while searching for the hips.
MAX_HIPS_SEARCH_DEPTH = 12
#: Maximum number of spine or neck joints supported (HumanIK: Spine..Spine9).
MAX_CHAIN_JOINTS = 10

# --- Retargeting ------------------------------------------------------------------

#: Minimum normalised mesh similarity (%) required to copy a rig and its weights.
MESH_SIMILARITY_THRESHOLD = 80.0
#: Surface distance tolerance as a fraction of normalised mesh height.
MESH_SIMILARITY_TOLERANCE = 0.03

#: Height ratios outside this range usually mean a unit mismatch (cm vs m).
SUSPICIOUS_SCALE_RATIO_MIN = 0.2
SUSPICIOUS_SCALE_RATIO_MAX = 5.0
