"""v12.5.4-D: plan-view A1/A2 abutments from a millimetre DXF template.

Local X is the bridge longitudinal axis; local Y is the left transverse axis.
The original DXF origin (0,0) is the placement anchor. Source is read-only.
"""
from __future__ import annotations
from pathlib import Path
import math
import ezdxf

LAYER = 'BRIDGE_ABUTMENT_PLAN'
DEFAULT_TEMPLATE = Path(__file__).with_name('교대일반도.dxf')


def read_template(path):
    doc = ezdxf.readfile(str(path))
    entities = []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == 'LINE':
            entities.append(('LINE', [(float(entity.dxf.start.x), float(entity.dxf.start.y)),
                                      (float(entity.dxf.end.x), float(entity.dxf.end.y))], False))
        elif kind == 'LWPOLYLINE':
            points = entity.get_points('xyb')
            if any(abs(float(bulge)) > 1e-10 for _, _, bulge in points):
                raise ValueError('교대 DXF의 곡선(bulge) 폴리라인은 아직 지원하지 않습니다.')
            entities.append(('LWPOLYLINE', [(float(x), float(y)) for x,y,_ in points], bool(entity.closed)))
        else:
            raise ValueError(f'교대 DXF에 미지원 객체 {kind}가 있습니다. LINE/LWPOLYLINE만 남기세요.')
    if not entities:
        raise ValueError('교대 DXF에 LINE 또는 LWPOLYLINE 객체가 없습니다.')
    if any(not all(math.isfinite(c) for xy in coords for c in xy) for _,coords,_ in entities):
        raise ValueError('교대 DXF 좌표에 유효하지 않은 숫자가 있습니다.')
    return entities


def draw_plan_abutments(msp, structures, *, points, distances, position_at,
                        station_origin=0.0, template_path=None):
    """Place A1 at bridge start, A2 at end. Convert template mm to plan metres.

    A2 mirrors the template local X only; local Y remains unchanged.
    Geometry is rotated by each station's actual FL tangent.
    """
    bridges = [s for s in structures if s.kind == 'BRIDGE']
    if not bridges:
        return {'abutments': 0, 'entities': 0}
    source = Path(template_path) if template_path else DEFAULT_TEMPLATE
    if not source.is_file():
        raise FileNotFoundError(f'교대 평면 템플릿 DXF를 찾을 수 없습니다: {source}')
    geometry = read_template(source)
    if LAYER not in msp.doc.layers:
        msp.doc.layers.new(LAYER, dxfattribs={'color': 1})
    counts = {'abutments': 0, 'entities': 0}
    for bridge in bridges:
        for side, sta in (('A1', bridge.start_sta), ('A2', bridge.end_sta)):
            (ox, oy), (tx, ty) = position_at(sta - station_origin, points, distances)
            direction = 1.0 if side == 'A1' else -1.0
            def transform(xy):
                u = direction * xy[0] / 1000.0
                v = xy[1] / 1000.0
                return (ox + tx*u - ty*v, oy + ty*u + tx*v)
            for kind, coords, closed in geometry:
                transformed = [transform(xy) for xy in coords]
                if kind == 'LINE':
                    msp.add_line(transformed[0], transformed[1], dxfattribs={'layer': LAYER})
                else:
                    msp.add_lwpolyline(transformed, close=closed, dxfattribs={'layer': LAYER})
                counts['entities'] += 1
            counts['abutments'] += 1
    return counts
