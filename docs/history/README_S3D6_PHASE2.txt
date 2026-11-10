Sierra v2.0 — S3-D6 Phase 2 (2026-11-03)

Modified:
- profile_presets/runtime.py (new): validate v2 and translate to the stable internal drawing contract; does not mutate user preset.
- profile_drawing.py: translate schema v2 once at the drawing entry point, before old drawing code accesses layout fields.
- main_gui.py: avoid KeyError on v2's removed expansion section; print selected schema/version and preset filename.
- test_s3d6_runtime.py (new): mapping, immutability and actual DXF entity equality against the v1 H5000/V1000 baseline when visibility settings match.

User-facing JSON v2 remains nested. Its deleted legacy groups are not reintroduced to JSON.
The existing CAD h5000_v1000.json remains schema v1 for safety. To opt in to v2 after backing up the current preset, copy h5000_v1000_schema_v2.json to profile_presets/cad/h5000_v1000.json.
IMPORTANT: bundled v2 example has visibility options different from frozen v1 (vertical_curve_details and vertical_curve_annotations are true; datum_labels in visibility_policy is false). If comparing drawings, align these options first.
The runtime translator is transitional; a future refactor may replace old drawing code's internal schema with v2 directly.

Run from project root:
  python -m unittest discover -p "test_*.py" -q

The test fixture uses an artificial profile, not the user's actual sample DXF. Verify the Windows GUI against the original H5000/V1000 sample before freezing this phase.
