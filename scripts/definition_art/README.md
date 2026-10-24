# RigFlow definition art

`geom.py` contains the silhouette and joint geometry, `style.py` contains the
style values, `gen.py` writes the SVG/layout assets, and `render.py` produces
reference mockups. They are the source of truth for `assets/definition/`.

From a Git Bash prompt, regenerate the committed assets and mockups with:

```sh
MAYAPY="C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe" \
  RIGFLOW_MOCKUPS="C:/Users/User/Temp/rigflow_definition_art" \
  ./scripts/definition_art/run.sh
```

Use Maya 2023's `mayapy.exe` when validating that version. The command writes
`body.svg`, `hands.svg`, and `layout.json` into `assets/definition/`; mockups
are written to `RIGFLOW_MOCKUPS`. It runs the generator twice because label
minimum scales are measured by the renderer before being written to the final
layout. The generated SVG/layout files are expected to be byte-for-byte equal
to the committed assets.
