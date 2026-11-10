Sierra S3-D7.2 — curve_offset trial

Changes:
- alignment_band.py: diagram.curve_offset controls signed diagram amplitude while keeping turn direction from alignment_reader.py.
- profile_presets/v2.py: optional nonnegative finite curve_offset validation.
- test_s3d72_curve_offset.py: 4 regression tests.
- h5000_v1000_S3D7_2_user_baseline.json: based on the user's h5000_v1000(3).json, with curve_offset: 6.0 added.

Windows GUI verification:
1. Back up the current Sierra directory and profile_presets/cad/h5000_v1000.json.
2. Extract this ZIP into a separate trial directory or merge code changes into a backup copy.
3. Copy h5000_v1000_S3D7_2_user_baseline.json to profile_presets/cad/h5000_v1000.json to activate the user's v2 baseline.
4. Run the GUI using the same DXF input. Confirm curve_offset=6 matches prior output.
5. Change curve_offset to 12; verify right curves +12 and left curves -12 relative to baseline_offset=40, with straight geometry unchanged.
6. Set curve_offset=0 and verify curve diagram collapses to baseline; restore 6 afterwards.

The default cad/h5000_v1000.json inside the archive remains the original v1 file to protect legacy automated tests. The user's current v2 baseline is included separately as noted above.
Automated tests: python -m unittest discover -p 'test_*.py' -q
Validated in container with Python 3.13, 96/96 tests passed. Windows GUI validation pending.
