Sierra v2.0 S3-D6 / phase 1: preset loader migration (trial)

Patch contents:
  profile_presets/loader.py  : schema_version 1 and 2 validation/loading
  profile_presets/v2.py      : strict nested schema v2 layout validator
  h5000_v1000_schema_v2.json: user-approved v2 nested JSON draft, not installed over existing v1
  test_s3d6_loader.py       : five schema v2 unit tests

Installation: copy loader.py and v2.py into existing Sierra/profile_presets/.
Keep existing schema.py, existing preset files and GUI unchanged.
Do NOT overwrite profile_presets/cad/h5000_v1000.json yet.
The v2 draft is a fixture until the drawing engine and GUI have been migrated.

Validation in this isolated test environment: 5/5 v2 tests pass; existing v1 H5000 JSON validates.
No Windows GUI/DXF equivalence test has been performed.

Note: Existing S3-D5.3 drawing code still accesses legacy paths. A v2 JSON may load,
but rendering it with unmodified drawing code is not supported.
