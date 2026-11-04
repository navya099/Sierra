Sierra v2 S3-D8.3 GUI trial

Structure profile label text.title and text.station support x_offset/y_offset measured in output drawing units relative to A: the top of the vertical leader and start of the sloped leader.
Coordinates are global XY, unaffected by text.rotation.
The leader geometry is not changed when moving labels.
Legacy title_offset_factor and station_offset_factor remain supported when the corresponding new object is absent.
CAD H5000/V1000 baseline has converted the former factor offsets to numerically equivalent XY coordinates to preserve the previous drawing.

Verification: 121 tests run, 120 pass, 1 existing test_s3d6_runtime.test_legacy_no_mutation fails because it expects schema v1 while the baseline file is schema v2. Windows GUI verification pending.
