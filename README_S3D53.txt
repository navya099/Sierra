Sierra v2.0 S3-D5.3 — annotation dimension preset (trial)

Overlay into D:\git\Sierra (back up first).
Files: profile_drawing.py, profile_presets/loader.py, profile_presets/cad/h5000_v1000.json, test_s3d53_annotations.py

CAD H5000/V1000 layout.annotations.enabled is FALSE by default.
Set TRUE to customize 17 drawing-space annotation parameters; existing dimensions are the defaults.
Does not change S3-C station/elevation coordinate transforms, bridge/tunnel geometry, or H1000/V400 baseline.

Tests:
python -m unittest -v test_s3d53_annotations.py test_s3d52_absolute.py test_s3d5_expansion.py test_s3d4_visibility.py test_s3d3_placement.py test_s3d2_preset_dxf.py test_s3d1_presets.py test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py

Notes:
- test_s3d53_annotations.py imports the existing test_preset_fixture and test_s3d2_preset_dxf modules.
- S3-D5.3 covers annotation positions and text heights in profile_drawing.py. Bridge/tunnel and alignment-band external modules remain for a later phase.
- The provided CAD H5000/V1000 JSON is a template: preserve your customized operational preset by copying only the layout.annotations object into it, instead of overwriting the entire JSON.
