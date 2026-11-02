Sierra v2.0 S3-D5: OPTIONAL expanded drawing-space layout

Copy profile_drawing.py, profile_presets/, test_s3d5_expansion.py into Sierra root.
S3-D4 and earlier files are retained.

S3-D5 layout.expansion (per CAD/REPORT preset):
 enabled: false by default (protects baseline and previous regression tests)
 band_height_factor: multiplies all five band rows and two rule offsets
 label_column_width: absolute drawing-space left band column width
 text_height_factor: scales band text sizes and annotation row height
 profile_plot_height: exact graph upper-minus-lower size
 use_placement_clearance: derive lower from expanded band plus S3-D3 reservations

IMPORTANT: H5000/V1000 and H25000/V5000 factors (5x) are PROVISIONAL
illustrative values, NOT extracted exact sample dimensions.
CAD 1:1 station X and REPORT X=1000/H remain unchanged.
No GUI wiring; enable explicitly by changing a copied JSON preset.
Structure collision prevention is reservation-based, not geometric.

TEST: python -m unittest -v test_s3d5_expansion.py test_s3d4_visibility.py test_s3d3_placement.py test_s3d2_preset_dxf.py test_s3d1_presets.py test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py
