Sierra v2.0 S3-D3 — opt-in preset-based band/profile vertical placement (trial)

Apply to S3-D2 project:
  1. Backup profile_drawing.py and profile_presets/.
  2. Copy profile_drawing.py, profile_presets/ and test_s3d3_placement.py from ZIP into Sierra root.
  3. Run:
     python -m unittest -v test_s3d3_placement.py test_s3d2_preset_dxf.py test_s3d1_presets.py test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py

All six JSON presets have layout.placement with enabled=false by default.
When enabled=true, graph lower edge is raised as necessary:
  plot_lower_y = max(existing plot_lower_y, sum(band row heights) + band_to_profile_gap
                     + reserved_structure_depth + structure_clearance)
  plot_upper_y = max(existing plot_upper_y, plot_lower_y + profile_plot_height)
Band rows remain anchored at the original band origin. Datum calculations, profile,
structure geometry, and grid use the resulting lower/upper graph limits.

Example (CAD H5000/V1000):
  from profile_presets.loader import load_preset
  from profile_drawing import DrawingOptions, create_profile_drawing
  from profile_transform import DrawingMode
  p=load_preset('cad',5000,1000)
  p['layout']['placement'].update(enabled=True, reserved_structure_depth=250)
  opts=DrawingOptions(drawing_mode=DrawingMode.CAD, horizontal_scale=5000,
                      vertical_scale=1000, layout_preset=p)
  create_profile_drawing('input.dxf','output.dxf',opts)

IMPORTANT LIMITATIONS:
- reserved_structure_depth is an explicit DXF-coordinate-unit reservation,
  NOT automatically measured from actual bridge piers/tunnel geometry. It is
  user/preset-supplied. No claim of collision-free output with real structures.
- datum_label_offset is recorded and validated for later annotation integration,
  but existing datum label placement is NOT changed in D3.
- S3-D3 does NOT implement detailed/simplified/overview visibility policies.
- No GUI changes; layout preset remains explicit opt-in, like S3-D2.
- Existing H1000/V400 baseline stays unchanged with placement.enabled=false.
- CAD DXF X coordinates remain 1:1. REPORT scaling is untouched.
- This is a first placement foundation, not a complete automatic collision solver.
