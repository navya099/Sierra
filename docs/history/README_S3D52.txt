Sierra S3-D5.2 absolute-dimension layout trial

Copy profile_drawing.py, profile_presets/, test_s3d52_absolute.py into your Sierra project.
CAD H5000/V1000 absolute_dimensions.enabled=true, provisional 5x-equivalent dimensions.
Other presets absolute_dimensions.enabled=false; no change unless explicitly enabled.
The legacy expansion remains supported for backward compatibility but is not used when absolute_dimensions is enabled.
For user-specific layout edit layout.absolute_dimensions.band/text/sheet/profile directly.
NOTE: structure clearance is still a preset reservation, not geometry collision detection.
GUI must call options_with_preset() before drawing (as fixed in S3-D5.1).
Run: python -m unittest -v test_s3d52_absolute.py test_s3d5_expansion.py test_s3d4_visibility.py test_s3d3_placement.py test_s3d2_preset_dxf.py test_s3d1_presets.py test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py
