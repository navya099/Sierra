"""v12.5.5-C: plan-view tunnel inner/outer footprints, one per tunnel."""
from __future__ import annotations
import math

OUTER_LAYER = 'TUNNEL_OUTER_PLAN'
INNER_LAYER = 'TUNNEL_INNER_PLAN'

def draw_tunnel_plan(msp, structures, *, points, distances, position_at,
                     station_origin=0.0, section=None, sample_step=2.0,
                     default_half_width=5.0, lining_thickness=0.2):
    if not all(math.isfinite(x) for x in (station_origin, sample_step, default_half_width, lining_thickness)):
        raise ValueError('터널 평면 설정에 유한하지 않은 값이 있습니다.')
    if sample_step <= 0 or default_half_width <= 0 or not 0 <= lining_thickness < default_half_width:
        raise ValueError('터널 평면 폭, 라이닝 두께, 샘플 간격을 확인하세요.')
    if section is not None:
        section.validate()
        offsets = ((section.outer_left, section.outer_right), (section.inner_left, section.inner_right))
    else:
        offsets = ((-default_half_width, default_half_width),
                   (-default_half_width + lining_thickness, default_half_width - lining_thickness))
    for layer, color in ((OUTER_LAYER, 5), (INNER_LAYER, 4)):
        if layer not in msp.doc.layers:
            msp.doc.layers.new(layer, dxfattribs={'color': color})
    count = {'outer': 0, 'inner': 0}
    max_sta = station_origin + distances[-1]
    for structure in structures:
        if structure.kind != 'TUNNEL':
            continue
        a, b = structure.start_sta, structure.end_sta
        if not all(math.isfinite(x) for x in (a,b)) or a < station_origin-1e-6 or b > max_sta+1e-6 or a >= b:
            raise ValueError(f'터널 {structure.name} 측점이 FL 범위 밖입니다: {a:g}~{b:g}')
        n = max(1, math.ceil((b-a)/sample_step))
        stations = [a+(b-a)*i/n for i in range(n+1)]
        stations += [station_origin+d for d in distances[1:-1] if a+1e-8 < station_origin+d < b-1e-8]
        stations = sorted(set(stations))
        def edge(offset):
            result = []
            for sta in stations:
                (x,y),(tx,ty) = position_at(sta-station_origin, points, distances)
                result.append((x-ty*offset,y+tx*offset))
            return result
        for (left,right),layer,key in zip(offsets,(OUTER_LAYER,INNER_LAYER),('outer','inner')):
            coords = edge(left) + list(reversed(edge(right)))
            msp.add_lwpolyline(coords, close=True, dxfattribs={'layer': layer})
            count[key] += 1
    return count
