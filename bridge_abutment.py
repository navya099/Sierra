"""Reference abutment geometry extracted from user-supplied Abutment.dxf.

Coordinates are preserved verbatim from the DXF modelspace. The reference
origin (0,0) is intended to coincide with the girder top at the bridge end.
User confirmed 1 drawing unit = 1 metre; DXF INSUNITS metadata is inaccurate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Point = tuple[float, float]
Segment = tuple[Point, Point]

# 18 LINE entities, in original DXF order. Units are source drawing units.
ABUTMENT_LINES: tuple[Segment, ...] = (((-4.0, -1.421626), (-4.0, -7.37873)), ((-0.5, 0.0), (-0.5, -2.181217)), ((-0.5, -2.181217), (-0.5, -7.37873)), ((1.3, -2.411246), (1.3, -7.37873)), ((0.0, -2.411246), (1.3, -2.411246)), ((0.0, 0.0), (0.0, -2.411246)), ((4.2, -7.37873), (1.3, -7.37873)), ((4.2, -8.44123), (4.2, -7.37873)), ((-5.0, -8.44123), (4.3, -8.44123)), ((-4.9, -7.37873), (-4.9, -8.44123)), ((-0.5, -7.37873), (-4.9, -7.37873)), ((4.3, -8.50373), (4.3, -8.44123)), ((-5.0, -8.50373), (4.3, -8.50373)), ((-5.0, -8.44123), (-5.0, -8.50373)), ((-6.0, -0.588293), (-4.0, -1.421626)), ((-6.0, 0.0), (-6.0, -0.588293)), ((0.0, 0.0), (0.0, -1.553746)), ((-6.0, 0.0), (0.0, 0.0)))

ABUTMENT_BOUNDS = (-6.0, -8.50373, 4.3, 0.0)  # xmin,ymin,xmax,ymax
SOURCE_DXF_INSUNITS = 1  # Source metadata only; user confirms geometry in metres


def transformed_lines(
    origin_sta: float,
    origin_elevation: float,
    side: Literal['A1', 'A2'] = 'A1',
    scale: float = 1.0,
) -> list[Segment]:
    """Return transformed line segments for the longitudinal profile.

    A1: local +X points toward increasing station.
    A2: local +X points toward decreasing station (horizontal mirror).
    The reference geometry is preserved; no geometry distortion or clipping.
    """
    if side not in ('A1', 'A2'):
        raise ValueError('side must be A1 or A2')
    if scale <= 0:
        raise ValueError('scale must be positive')
    direction = 1 if side == 'A1' else -1
    def transform(p: Point) -> Point:
        return (origin_sta + direction * scale * p[0],
                origin_elevation + scale * p[1])
    return [(transform(a), transform(b)) for a, b in ABUTMENT_LINES]


def draw_abutment(msp, origin_sta: float, origin_elevation: float,
                  side: Literal['A1','A2']='A1',
                  layer: str='BRIDGE_ABUTMENT', scale: float=1.0) -> int:
    """Add 18 LINE entities to an ezdxf modelspace. Returns entity count."""
    if layer not in msp.doc.layers:
        msp.doc.layers.new(layer, dxfattribs={'color': 1})
    segments = transformed_lines(origin_sta, origin_elevation, side, scale)
    for a, b in segments:
        msp.add_line(a, b, dxfattribs={'layer': layer})
    return len(segments)


def draw_profile_abutments(msp, structures, settings, start, end, datum_segments,
                           elevation_at, display_sta, display_el, vertical_exaggeration,
                           layer='BRIDGE_ABUTMENT'):
    """Draw A1/A2 at global bridge ends; output-only Y exaggeration.

    Abutments are drawn only on the sheet containing their anchor station.
    A datum boundary is resolved by preferring the segment interior to the bridge.
    """
    import math
    if not math.isfinite(vertical_exaggeration) or vertical_exaggeration <= 0:
        raise ValueError('vertical_exaggeration must be positive')
    if layer not in msp.doc.layers:
        msp.doc.layers.new(layer, dxfattribs={'color': 1})
    count = 0
    for structure in structures or []:
        if structure.kind != 'BRIDGE':
            continue
        for side, station in (('A1', structure.start_sta), ('A2', structure.end_sta)):
            # One owner sheet at a split boundary: A1 on following sheet, A2 on preceding.
            if not (start - 1e-7 <= station <= end + 1e-7):
                continue
            if side == 'A1' and station >= end - 1e-7:
                continue
            if side == 'A2' and station <= start + 1e-7:
                continue
            interior = station + (1e-6 if side == 'A1' else -1e-6)
            datum = next((seg for seg in datum_segments
                          if seg.start_sta - 1e-7 <= interior <= seg.end_sta + 1e-7), None)
            if datum is None:
                continue
            x0 = display_sta(station)
            y0 = display_el(elevation_at(station)-settings.girder_top_offset, datum.datum_el)
            direction = 1 if side == 'A1' else -1
            for (ax,ay),(bx,by) in ABUTMENT_LINES:
                a=(x0 + direction*ax, y0 + vertical_exaggeration*ay)
                b=(x0 + direction*bx, y0 + vertical_exaggeration*by)
                msp.add_line(a,b,dxfattribs={'layer':layer})
            count += 1
    return count
