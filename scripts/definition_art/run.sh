#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MAYAPY="${MAYAPY:-C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe}"
ASSETS="${RIGFLOW_ASSETS:-$ROOT/assets/definition}"
MOCKUPS="${RIGFLOW_MOCKUPS:-${TEMP:-/tmp}/rigflow_definition_art}"
mkdir -p "$ASSETS" "$MOCKUPS"

# The first render measures collision-free label minimum scales.  The second
# generator writes those values into the final layout, then the final render
# produces mockups from exactly that committed layout.
"$MAYAPY" -I "$ROOT/scripts/definition_art/gen.py" "$ASSETS"
"$MAYAPY" -I "$ROOT/scripts/definition_art/render.py" "$ASSETS" "$MOCKUPS"
RIGFLOW_MIN_SCALES="$MOCKUPS/_min_scales.json" \
  "$MAYAPY" -I "$ROOT/scripts/definition_art/gen.py" "$ASSETS"
"$MAYAPY" -I "$ROOT/scripts/definition_art/render.py" "$ASSETS" "$MOCKUPS"
