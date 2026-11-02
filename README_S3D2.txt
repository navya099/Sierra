Sierra S3-D2 — explicit opt-in DXF layout preset integration

Copy profile_drawing.py and profile_presets/ into D:\git\Sierra (backup first).
Do not overwrite main_gui.py, profile_layout.py or profile_transform.py.

Default DrawingOptions() produces the legacy drawing unchanged.
To opt in: from profile_drawing import options_with_preset
options = options_with_preset(DrawingOptions(...))
create_profile_drawing(source, target, options=options)
Preset mode and scales must match the selected DrawingOptions exactly.

Only baseline H1000/V400 is intended for regression freeze. H5000 and H25000
presets remain provisional and are not layout-approved. GUI hookup is deferred.

Run: python -m unittest -v test_s3d2_preset_dxf.py test_s3d1_presets.py test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py
