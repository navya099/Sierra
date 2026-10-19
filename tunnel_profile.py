"""v12.5.5-A: longitudinal tunnel body, independent of portal geometry."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class TunnelSettings:
    bottom_offset: float = 2.0   # metres below design profile
    body_height: float = 9.0     # metres, total vertical body height
    sample_step: float = 2.0     # metres along station
    color: int = 5              # AutoCAD ACI

    def validate(self):
        if not all(math.isfinite(x) for x in (self.bottom_offset,self.body_height,self.sample_step)):
            raise ValueError('터널 치수는 유한한 숫자여야 합니다.')
        if self.bottom_offset < 0 or self.body_height <= 0 or self.sample_step <= 0:
            raise ValueError('터널 하부 OFFSET은 0 이상, 본체 높이와 샘플 간격은 양수여야 합니다.')
        if type(self.color) is not int or not 1 <= self.color <= 255:
            raise ValueError('터널 레이어 ACI 색상은 1~255 정수여야 합니다.')


def draw_tunnel_bodies(msp, structures, settings, start, end, datum_segments,
                       elevation_at, display_sta, display_el, layer='TUNNEL_BODY'):
    """One closed polyline per visible tunnel/datum segment; no portal.

    Splitting at sheet and datum boundaries prevents drawing across a datum jump.
    Station/elevation inputs are in metres; output transforms supplied by caller.
    """
    settings.validate()
    count=0
    for structure in structures:
        if structure.kind != 'TUNNEL':
            continue
        a0,b0=structure.start_sta,structure.end_sta
        if not all(math.isfinite(v) for v in (a0,b0)) or b0 <= a0:
            raise ValueError('터널 구조물의 시작/종료 측점을 확인하세요.')
        for datum in datum_segments:
            lo=max(a0,start,datum.start_sta)
            hi=min(b0,end,datum.end_sta)
            if hi-lo <= 1e-8:
                continue
            n=max(1,math.ceil((hi-lo)/settings.sample_step))
            stations=[lo+(hi-lo)*i/n for i in range(n+1)]
            top=[(display_sta(s),display_el(elevation_at(s)-settings.bottom_offset+settings.body_height,datum.datum_el)) for s in stations]
            bottom=[(display_sta(s),display_el(elevation_at(s)-settings.bottom_offset,datum.datum_el)) for s in reversed(stations)]
            msp.add_lwpolyline(top+bottom,close=True,dxfattribs={'layer':layer})
            count+=1
    return count
