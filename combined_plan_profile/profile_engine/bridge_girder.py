"""Simple longitudinal bridge girders. Stations/elevations in metres; output is drawing units."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class GirderSettings:
    girder_h: float = 2.0
    girder_length: float = 30.0
    girder_top_offset: float = 0.0
    girder_sample_step: float = 2.0

    def validate(self):
        if not all(math.isfinite(v) for v in (self.girder_h, self.girder_length, self.girder_top_offset, self.girder_sample_step)):
            raise ValueError('거더 설정은 유한한 숫자여야 합니다.')
        if self.girder_h <= 0 or self.girder_length <= 0 or self.girder_sample_step <= 0 or self.girder_top_offset < 0:
            raise ValueError('거더 높이/경간/샘플 간격은 양수, 상단 이격은 0 이상이어야 합니다.')


def span_ranges(start, end, nominal):
    """Even temporary spans, each <= nominal. Never create tiny leftover span."""
    n = max(1, math.ceil((end-start)/nominal - 1e-10))
    return [(start+(end-start)*i/n, start+(end-start)*(i+1)/n) for i in range(n)]


def draw_bridge_girders(msp, structures, settings, start, end, datum_segments,
                        elevation_at, display_sta, display_el, layer='BRIDGE_GIRDER'):
    """Clip by sheet AND datum. Preserve globally determined span boundaries."""
    settings.validate()
    count = 0
    for structure in structures:
        if structure.kind != 'BRIDGE':
            continue
        if not (math.isfinite(structure.start_sta) and math.isfinite(structure.end_sta)) or structure.end_sta <= structure.start_sta:
            raise ValueError('교량 구조물의 시작/종료 측점을 확인하세요.')
        for span_a, span_b in span_ranges(structure.start_sta, structure.end_sta, settings.girder_length):
            a, b = max(start,span_a), min(end,span_b)
            if b-a <= 1e-8:
                continue
            for datum in datum_segments:
                lo,hi=max(a,datum.start_sta),min(b,datum.end_sta)
                if hi-lo <= 1e-8:
                    continue
                n=max(1,math.ceil((hi-lo)/settings.girder_sample_step))
                stations=[lo+(hi-lo)*i/n for i in range(n+1)]
                top=[(display_sta(s),display_el(elevation_at(s)-settings.girder_top_offset,datum.datum_el)) for s in stations]
                bottom=[(display_sta(s),display_el(elevation_at(s)-settings.girder_top_offset-settings.girder_h,datum.datum_el)) for s in reversed(stations)]
                msp.add_lwpolyline(top+bottom,close=True,dxfattribs={'layer':layer})
                count += 1
    return count
