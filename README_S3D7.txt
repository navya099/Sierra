Sierra v2.0 S3-D7.1 alignment-band JSON trial

1. The GUI's existing cad/h5000_v1000.json is preserved as the S3-D6 v1 default.
2. To test schema v2 with S3-D7 alignment controls, back up
   profile_presets/cad/h5000_v1000.json, then copy
   h5000_v1000_schema_v2.json to profile_presets/cad/h5000_v1000.json.
3. Start main_gui.py and select CAD H5000/V1000. For equivalence to the frozen
   baseline, match visibility and visibility_policy settings with your approved v1.
4. Edit layout.band.alignment.text keys to test station height/rotation,
   curve info height/spacing/left/right offsets, and curve element label size/offsets.
5. Run: python -m unittest discover -p "test_*.py" -q

Scope: S3-D7.1 JSON schema, internal mapping, alignment-band drawing settings.
No modifications to curve geometry, band offset computation or other structure modules.
The S3-D6 legacy v2 annotation alignment key is optional when the new band
alignment group is present. Old v2 without the group remains valid.

Validation: 92/92 unittest PASS in container (Python 3.13).
Windows GUI output equivalence and ON/OFF checks remain user verification tasks.
