"""v12.5.4-A: EQUAL-span, closed bridge slab/girder footprints on horizontal FL.

All widths and FL coordinates are metres (1:1). The built-in cross section is
only a schematic placeholder, NOT a construction-ready bridge design.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from bridge_girder import span_ranges

SLAB_LAYER = 'BRIDGE_SLAB_PLAN'
GIRDER_LAYER = 'BRIDGE_GIRDER_PLAN'

@dataclass(frozen=True)
class BridgePlanSection:
    slab_left: float = -6.0
    slab_right: float = 6.0
    girders: tuple[tuple[float, float], ...] = (
        (-5.0, -4.0), (-2.0, -1.0), (1.0, 2.0), (4.0, 5.0)
    )

    def validate(self):
        values = (self.slab_left, self.slab_right) + tuple(v for pair in self.girders for v in pair)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('교량 단면 치수는 유한한 숫자여야 합니다.')
        if self.slab_left >= self.slab_right or not self.girders:
            raise ValueError('슬래브 폭 및 거더 목록을 확인하세요.')
        for left, right in self.girders:
            if not self.slab_left <= left < right <= self.slab_right:
                raise ValueError('거더 외곽은 슬래브 폭 안에 있어야 합니다.')


def _edge_points(stations, offset, points, distances, position_at, station_origin):
    result = []
    for sta in stations:
        (x, y), (tx, ty) = position_at(sta-station_origin, points, distances)
        result.append((x-ty*offset, y+tx*offset))
    return result


def _closed_strip(stations, left, right, points, distances, position_at, station_origin):
    a = _edge_points(stations, left, points, distances, position_at, station_origin)
    b = _edge_points(stations, right, points, distances, position_at, station_origin)
    return a + list(reversed(b))


def draw_bridge_plan(msp, structures, *, points, distances, position_at,
                     station_origin=0.0, nominal_span=30.0, sample_step=2.0,
                     section: BridgePlanSection | None = None):
    """Draw each EQUAL span separately. Return slab and girder entity counts.

    For the piecewise-linear FL source, insert every FL vertex station into
    samples so offset boundaries honor source bends rather than skipping them.
    """
    section = section or BridgePlanSection()
    section.validate()
    if not all(math.isfinite(v) for v in (station_origin, nominal_span, sample_step)) or nominal_span <= 0 or sample_step <= 0:
        raise ValueError('교량 평면 경간/샘플 간격을 확인하세요.')
    for layer, color in ((SLAB_LAYER, 4), (GIRDER_LAYER, 2)):
        if layer not in msp.doc.layers:
            msp.doc.layers.new(layer, dxfattribs={'color': color})
    counts = {'slab': 0, 'girder': 0}
    max_sta = station_origin + distances[-1]
    for structure in structures:
        if structure.kind != 'BRIDGE':
            continue
        start, end = structure.start_sta, structure.end_sta
        if not all(math.isfinite(v) for v in (start, end)) or not station_origin-1e-6 <= start < end <= max_sta+1e-6:
            raise ValueError(f'교량 {structure.name or "(이름 없음)"} 측점이 FL 범위 밖입니다: {start:g}~{end:g}')
        for a, b in span_ranges(start, end, nominal_span):
            n = max(1, math.ceil((b-a)/sample_step))
            stations = [a+(b-a)*i/n for i in range(n+1)]
            stations.extend(station_origin+d for d in distances[1:-1] if a+1e-8 < station_origin+d < b-1e-8)
            stations = sorted(set(stations))
            msp.add_lwpolyline(_closed_strip(stations, section.slab_left, section.slab_right,
                points, distances, position_at, station_origin), close=True, dxfattribs={'layer': SLAB_LAYER})
            counts['slab'] += 1
            for left, right in section.girders:
                msp.add_lwpolyline(_closed_strip(stations, left, right, points, distances,
                    position_at, station_origin), close=True, dxfattribs={'layer': GIRDER_LAYER})
                counts['girder'] += 1
    return counts
