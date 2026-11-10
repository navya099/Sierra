Sierra Phase 3 / v2.0-S1 — coordinate transform isolation (trial)

This is a PATCH, not a complete standalone Sierra project.
Files are based on the uploaded main-branch profile_drawing.py,
profile_layout.py, profile_scale.py. They may differ from your live branch.

Changes:
- New profile_transform.py centralizes station/elevation output coordinate formulas.
- profile_drawing.py delegates display_sta/display_el and vertical exaggeration to it.
- profile_layout.py and profile_scale.py are copied unchanged for reference.
- No change to existing output coordinate conventions, units, band, datum, or structures.

Installation: compare with your current feature branch before replacing any files.
Put profile_transform.py beside profile_drawing.py and apply the diff for
profile_drawing.py. Do not overwrite a newer file without reviewing differences.

Run: python -m unittest -v test_profile_transform.py
Next: compare full DXF outputs H1000/V400 on identical test inputs.
