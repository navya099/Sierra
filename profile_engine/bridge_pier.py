"""Parametric longitudinal bridge piers (metres, output-only vertical exaggeration)."""
from dataclasses import dataclass
import math
from bridge_girder import span_ranges

@dataclass(frozen=True)
class PierSettings:
    pier_width: float = 2.0
    cap_height: float = 1.5
    footing_width: float = 6.0
    footing_height: float = 1.5
    embed_depth: float = 2.0

    def validate(self):
        values=(self.pier_width,self.cap_height,self.footing_width,self.footing_height,self.embed_depth)
        if not all(math.isfinite(v) for v in values) or any(v <= 0 for v in values[:4]) or self.embed_depth < 0:
            raise ValueError('교각 폭/코핑부 높이/기초 폭/기초 높이는 양수, 매입 깊이는 0 이상이어야 합니다.')
        if self.footing_width < self.pier_width:
            raise ValueError('기초 폭은 교각 폭 이상이어야 합니다.')


def draw_profile_piers(msp, structures, girder_settings, pier_settings, start, end,
                       datum_segments, elevation_at, ground_at, display_sta,
                       display_el, vertical_exaggeration, layer='BRIDGE_PIER'):
    """Place one pier at each global internal EQUAL span boundary.

    A pier belongs to the sheet [start,end), except at the final drawing end.
    The entire pier is placed on its anchor sheet, like abutments; no clipping.
    """
    girder_settings.validate(); pier_settings.validate()
    if not math.isfinite(vertical_exaggeration) or vertical_exaggeration <= 0:
        raise ValueError('수직 과장률은 양수여야 합니다.')
    if layer not in msp.doc.layers:
        msp.doc.layers.new(layer, dxfattribs={'color': 1})
    count=0
    for bridge in structures or []:
        if bridge.kind != 'BRIDGE': continue
        spans=span_ranges(bridge.start_sta,bridge.end_sta,girder_settings.girder_length)
        for i in range(len(spans)-1):
            station=spans[i][1]
            if station < start-1e-7 or station > end+1e-7: continue
            if station >= end-1e-7 and end < bridge.end_sta-1e-7: continue
            datum=next((d for d in datum_segments if d.start_sta-1e-7 <= station <= d.end_sta+1e-7),None)
            if datum is None: continue
            top=elevation_at(station)-girder_settings.girder_top_offset-girder_settings.girder_h
            footing_top=ground_at(station)-pier_settings.embed_depth
            cap_bottom=top-pier_settings.cap_height
            if cap_bottom <= footing_top:
                raise ValueError(f'교각 P{i+1} (STA {station:.3f}): 코핑부 하단이 기초 상단보다 낮습니다. 지반/거더/치수를 확인하세요.')
            x0=display_sta(station)
            def pt(x,z): return (x0+x, display_el(top,datum.datum_el)+vertical_exaggeration*(z-top))
            def rectangle(width,zlo,zhi):
                w=width/2
                msp.add_lwpolyline([pt(-w,zlo),pt(w,zlo),pt(w,zhi),pt(-w,zhi)],close=True,dxfattribs={'layer':layer})
            rectangle(pier_settings.pier_width,footing_top,top)
            rectangle(pier_settings.footing_width,footing_top-pier_settings.footing_height,footing_top)
            # Cap boundary and two optional inner cylinder representation lines.
            w=pier_settings.pier_width/2
            msp.add_line(pt(-w,cap_bottom),pt(w,cap_bottom),dxfattribs={'layer':layer})
            for fraction in (-0.35,0.35):
                msp.add_line(pt(w*fraction,cap_bottom),pt(w*fraction,footing_top),dxfattribs={'layer':layer})
            count+=1
    return count
