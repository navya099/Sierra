Sierra v2.0 S3-D5.2.1 — Regression test isolation / priority verification

Purpose:
- Tests use immutable, bundled test_fixtures/profile_presets/*.json snapshots rather than editable production JSON.
- S3-D5.2 absolute dimension test sets explicit band dimensions and graph placement inputs.
- S3-D3 placement and S3-D5 expansion tests disable other opt-in modes via fixture presets.
- New test verifies absolute_dimensions takes precedence over expansion and placement even if all enabled, and does not mutate the input preset.
- Production profile_drawing.py, profile_presets/*.json, and GUI are NOT modified by this patch.

Apply:
- Unzip into D:\git\Sierra, preserving subdirectories.
- Overwrite four test_*.py files, add test_preset_fixture.py and test_fixtures folder.
- Do NOT overwrite any production preset JSON. User-edited CAD H5000/V1000 absolute_dimensions.enabled=True is preserved.

Run:
python -m unittest -v test_s3d52_absolute.py test_s3d5_expansion.py test_s3d4_visibility.py test_s3d3_placement.py test_s3d2_preset_dxf.py test_s3d1_presets.py test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py

Local test: 51 tests OK (Python 3.13, ezdxf 1.4.4). Windows 3.11 validation pending.
Note: Existing TemporaryDirectory ResourceWarnings are unrelated and not addressed in this patch.
