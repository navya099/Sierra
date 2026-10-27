"""v12.5.5-A: longitudinal tunnel body, independent of portal geometry."""
from dataclasses import dataclass
from .tunnel_section import TunnelSection
from .tunnel_portal import PortalSettings
import math

@dataclass(frozen=True)
class TunnelSettings:
    bottom_offset: float = 2.0   # metres below design profile
    body_height: float = 9.0     # metres, total vertical body height
    sample_step: float = 2.0     # metres along station
    color: int = 5              # AutoCAD ACI
    lining_thickness: float = 0.2  # metres; inner envelope inset
    section: TunnelSection | None = None  # optional exact vertical extrema from DXF
    portal: PortalSettings | None = None  # optional built-in longitudinal portals

    def validate(self):
        if not all(math.isfinite(x) for x in (self.bottom_offset,self.body_height,self.sample_step,self.lining_thickness)):
            raise ValueError('터널 치수는 유한한 숫자여야 합니다.')
        if self.bottom_offset < 0 or self.body_height <= 0 or self.sample_step <= 0:
            raise ValueError('터널 하부 OFFSET은 0 이상, 본체 높이와 샘플 간격은 양수여야 합니다.')
        if self.lining_thickness < 0 or 2*self.lining_thickness >= self.body_height:
            raise ValueError('라이닝 두께는 0 이상이고 본체 높이 절반보다 작아야 합니다.')
        if self.section is not None:
            self.section.validate()
        if self.portal is not None:
            self.portal.validate()
        if type(self.color) is not int or not 1 <= self.color <= 255:
            raise ValueError('터널 레이어 ACI 색상은 1~255 정수여야 합니다.')


def draw_tunnel_bodies(msp, structures, settings, start, end, datum_segments,
                       elevation_at, display_sta, display_el, layer='TUNNEL_BODY', inner_layer='TUNNEL_INNER'):
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
            outer_bottom = settings.section.outer_bottom if settings.section else -settings.bottom_offset
            outer_top = settings.section.outer_top if settings.section else -settings.bottom_offset+settings.body_height
            inner_bottom = settings.section.inner_bottom if settings.section else outer_bottom+settings.lining_thickness
            inner_top = settings.section.inner_top if settings.section else outer_top-settings.lining_thickness
            top=[(display_sta(s),display_el(elevation_at(s)+outer_top,datum.datum_el)) for s in stations]
            bottom=[(display_sta(s),display_el(elevation_at(s)+outer_bottom,datum.datum_el)) for s in reversed(stations)]
            msp.add_lwpolyline(top+bottom,close=True,dxfattribs={'layer':layer})
            t=settings.lining_thickness
            inner_top=[(display_sta(s),display_el(elevation_at(s)+inner_top,datum.datum_el)) for s in stations]
            inner_bottom=[(display_sta(s),display_el(elevation_at(s)+inner_bottom,datum.datum_el)) for s in reversed(stations)]
            msp.add_lwpolyline(inner_top+inner_bottom,close=True,dxfattribs={'layer':inner_layer})
            count+=2-1
    return count
