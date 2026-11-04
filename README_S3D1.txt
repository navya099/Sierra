Sierra v2.0-S3-D1: preset schema + loader (data-only trial)

Apply: copy profile_presets/ and test_s3d1_presets.py to D:\git\Sierra\.
Do not overwrite main_gui.py, profile_drawing.py, profile_layout.py or profile_transform.py.

Run: python -m unittest -v test_s3d1_presets.py test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py

CAD and REPORT each have three independent JSON files.
H1000/V400: layout values extracted from current ProfileLayout / DrawingOptions / band drawing code.
H5000/V1000, H25000/V5000: baseline dimensions COPIED TEMPORARILY; status=provisional. No claims of layout suitability.
visibility values are initial policy PROPOSALS only; not yet applied to drawing.

S3-D1 does not change actual DXF drawing or GUI. S3-D2 will wire H1000/V400 preset into rendering and verify regression before others.

Units: numeric layout fields are in the existing drawing coordinate system; CAD mode uses metres, REPORT uses millimetres. Physical and paper sizes must be independently calibrated in S3-D3/D5. The schema does not control the coordinate transform.
