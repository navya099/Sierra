Sierra v2.0-S3-B / DXF coordinate mode integration trial
==========================================================
Base: S1 profile_drawing.py + S3-A profile_transform.py.

Files:
  profile_drawing.py          Replace your S1 file (back up first).
  profile_transform.py        S3-A coordinate policy (same as S3-A).
  test_s3b_dxf_modes.py       Actual DXF integration tests.
  test_s3a_transform.py       S3-A coordinate tests.
  test_profile_transform.py   S1 legacy transform tests.

Usage:
  python -m unittest -v test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py

Programmatic example (GUI not yet wired):
  from profile_drawing import DrawingOptions, create_profile_drawing
  from profile_transform import DrawingMode
  opts = DrawingOptions(drawing_mode=DrawingMode.CAD,
                        horizontal_scale=5000, vertical_scale=1000,
                        vertical_exaggeration_enabled=True)
  create_profile_drawing('source.dxf', 'cad_result.dxf', options=opts)

Rules:
  CAD X: 1 DXF unit = 1 metre; Y = elevation difference * H/V (ON), or 1 (OFF).
  REPORT X: delta_sta * 1000/H; Y = delta_elev * 1000/V (ON),
            or delta_elev * 1000/H (OFF).
  CAD $INSUNITS=6 (metres), REPORT $INSUNITS=4 (millimetres).
  Existing DrawingOptions defaults remain REPORT+exaggeration ON to protect S1/S2 output.
  Automatic datum's elevation window uses effective Y-units/metre in both modes.

LIMITATIONS / IMPORTANT:
  - GUI has not yet been wired to drawing_mode and vertical_exaggeration_enabled.
    If your GUI calls DrawingOptions without those fields, it still creates REPORT DXF.
  - Annotation, band, label and titleblock physical dimensions are NOT yet reflowed
    for CAD mode. This trial validates profile coordinates and DXF units, not
    delivery-ready drawing aesthetics. Structural visual verification pending.
  - In CAD mode existing layout numeric dimensions become metre-valued coordinates;
    do not print or deliver as-is until the subsequent layout stage.
  - S3-A and S1/S2 regression tests pass. The test fixture does not include bridges/tunnels.
  - Do not apply to your main branch; use feature/profile-multiscale-v2.
