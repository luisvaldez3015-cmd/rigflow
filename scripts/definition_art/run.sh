#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MAYAPY="${MAYAPY:-C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe}"
ASSETS="${RIGFLOW_ASSETS:-$ROOT/assets/definition}"
MOCKUPS="${RIGFLOW_MOCKUPS:-${TEMP:-/tmp}/rigflow_definition_art}"
mkdir -p "$ASSETS" "$MOCKUPS"
export RIGFLOW_MIN_SCALES="${RIGFLOW_MIN_SCALES:-$MOCKUPS/_min_scales.json}"

# Measure collision-free label minimum scales, then write the final layout.
"$MAYAPY" -I "$ROOT/scripts/definition_art/gen.py" "$ASSETS"
"$MAYAPY" -I "$ROOT/scripts/definition_art/render.py" "$ASSETS" "$MOCKUPS"
"$MAYAPY" -I "$ROOT/scripts/definition_art/gen.py" "$ASSETS"
"$MAYAPY" -I "$ROOT/scripts/definition_art/render.py" "$ASSETS" "$MOCKUPS"
"$MAYAPY" -I "$ROOT/scripts/definition_art/compare.py" "$ASSETS" "$MOCKUPS/compare.png"
