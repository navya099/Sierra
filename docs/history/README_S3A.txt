Sierra v2.0 S3-A — Coordinate mode separation (core trial)

Prerequisite: S1 profile_transform.py already installed; S2/S3 GUI changes may remain.
Copy profile_transform.py to Sierra project root (replaces S1 file).
Copy test_s3a_transform.py to project root.
Run: python -m unittest -v test_s3a_transform.py test_profile_transform.py

New API:
  from profile_transform import ProfileTransform, DrawingMode
  cad = ProfileTransform(horizontal_scale=5000, vertical_scale=1000,
                         mode=DrawingMode.CAD,
                         vertical_exaggeration_enabled=True)
  report = ProfileTransform(horizontal_scale=5000, vertical_scale=1000,
                            mode=DrawingMode.REPORT)

Coordinate rules (input metres):
 CAD: X delta = station delta; Y delta = elevation delta * H/V (ON) or 1 (OFF)
 REPORT: X delta = station delta * 1000/H; Y delta = elevation delta * 1000/V (ON)
         or elevation delta * 1000/H (OFF)

IMPORTANT LIMITATIONS:
 - S3-A is a transform-layer trial, not full CAD-mode DXF output.
 - Existing profile_drawing.py calls ProfileTransform with no mode, so REPORT remains
   default for exact S1/S2 backward compatibility.
 - GUI, band geometry, annotations, bridge/tunnel dimensions, $INSUNITS and sheet
   geometry are NOT switched to CAD mode yet. Do not assume generated DXF is CAD 1:1.
 - S3-B will integrate mode into drawing pipeline and handle unit-dependent layout.
