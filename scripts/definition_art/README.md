# RigFlow definition art

The approved second-pass art uses an athletic A-pose body, two label columns
with leaders, and open hands with naturally spread fingers. `geom.py` contains
the silhouette, joint and label geometry; `style.py` contains the style values
and the generated `joint-style.md` documentation. `gen.py` writes the four
assets in `assets/definition/`. `render.py` measures collision-free label
minimum scales and produces reference mockups and a joint-state sheet.

From a Git Bash prompt, regenerate the committed assets and mockups with:

```sh
MAYAPY="C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe" \
  RIGFLOW_MOCKUPS="C:/Users/User/Temp/rigflow_definition_art_v2" \
  bash scripts/definition_art/run.sh
```

Use Maya 2023's `mayapy.exe` to validate that version. `RIGFLOW_ASSETS` can
redirect asset output for a clean reproducibility check. The script runs the
generator and renderer twice: the renderer measures label visibility, then
the generator writes those minimum scales into the final layout. The
`RIGFLOW_MIN_SCALES` cache defaults to the mockup directory, outside the repo.
All four generated assets use UTF-8 and LF and must match the checked-in
files byte-for-byte. Running `gen.py` alone without the measured cache writes
zero minimum scales; use `run.sh` for the complete generation cycle.

`compare.py` writes a silhouette/SVG comparison sheet. Optional local body
and hand reference images can be supplied with `RIGFLOW_ART_REFERENCES`
(a directory containing `body_reference.png` and `hand_reference.png`);
missing reference columns are omitted. These photos are not shipped.

The app paints SVG, leaders, bones, joints (waiting joint last), labels and
headings in that order. Label and leader visibility share `minScale`.
Leader width stays fixed in pixels; only their viewBox coordinates scale.
