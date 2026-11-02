Sierra v2.0 S3-D4 — opt-in display policy (trial)

Apply on top of S3-D3: replace profile_drawing.py and profile_presets/; add test_s3d4_visibility.py.
S3-C coordinate transform and S3-D3 layout placement unchanged.

Each of six CAD/REPORT presets has independent visibility_policy.
Default enabled=false preserves prior output exactly, even if individual flags are false.
To test, set visibility_policy.enabled=true in the selected JSON preset.
Then set selected groups false. Groups: minor_grid, vertical_curve_annotations,
vip_annotations, datum_labels, alignment_geometry, ground_profile,
design_profile, bridge_piers, bridge_abutments, bridge_girders,
structure_labels, tunnel_portals, tunnel_bodies.

This trial filters entities by DXF layer after geometry generation. It does NOT
simplify geometry, optimize computation, or alter structural quantity calculations.
Band numeric label density, station label spacing, and graph height expansion
are NOT changed in S3-D4; they belong to the next layout refinement.
Existing visibility flags are retained for backwards compatibility but the new
visibility_policy controls the opt-in layer filtering.

Run:
python -m unittest -v test_s3d4_visibility.py test_s3d3_placement.py test_s3d2_preset_dxf.py test_s3d1_presets.py test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py
