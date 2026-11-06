"""v12.5.4-C: schematic bridge pier/footing footprints on horizontal alignment."""
from dataclasses import dataclass
import math
from bridge_girder import span_ranges

COLUMN_LAYER = 'BRIDGE_PIER_COLUMN_PLAN'
COPING_LAYER = 'BRIDGE_PIER_COPING_PLAN'
FOUNDATION_LAYER = 'BRIDGE_FOUNDATION_PLAN'

@dataclass(frozen=True)
class PlanPierSettings:
    column_diameter: float = 3.0
    coping_width: float = 6.0       # local transverse dimension
    coping_length: float = 6.0      # local longitudinal dimension
    foundation_width: float = 9.0   # local transverse dimension
    foundation_length: float = 9.0  # local longitudinal dimension

    def validate(self):
        values=(self.column_diameter,self.coping_width,self.coping_length,
                self.foundation_width,self.foundation_length)
        if not all(math.isfinite(v) and v>0 for v in values):
            raise ValueError('평면 교각/기초 치수는 양수인 유한 숫자여야 합니다.')
        if min(self.coping_width,self.coping_length)<self.column_diameter:
            raise ValueError('코핑부는 기둥 지름보다 작을 수 없습니다.')
        if self.foundation_width<self.coping_width or self.foundation_length<self.coping_length:
            raise ValueError('기초는 코핑부보다 작을 수 없습니다.')


def draw_plan_piers(msp, structures, *, points, distances, position_at,
                    station_origin=0., nominal_span=30., settings=None):
    """Place one circular column, closed coping and closed footing at each
    internal EQUAL span boundary. Local x follows FL tangent, local y is left.
    No A1/A2 is generated. All units are metres (1:1).
    """
    settings=settings or PlanPierSettings()
    settings.validate()
    if not math.isfinite(nominal_span) or nominal_span<=0:
        raise ValueError('경간 길이는 양수여야 합니다.')
    for layer,color in ((COLUMN_LAYER,4),(COPING_LAYER,2),(FOUNDATION_LAYER,1)):
        if layer not in msp.doc.layers:
            msp.doc.layers.new(layer,dxfattribs={'color':color})
    counts={'column':0,'coping':0,'foundation':0}
    for structure in structures:
        if structure.kind!='BRIDGE':
            continue
        spans=span_ranges(structure.start_sta,structure.end_sta,nominal_span)
        for _,station in spans[:-1]:
            (x,y),(tx,ty)=position_at(station-station_origin,points,distances)
            def rectangle(layer, width, length):
                # u: longitudinal / v: transverse
                corners=((-length/2,-width/2),(length/2,-width/2),
                         (length/2,width/2),(-length/2,width/2))
                xy=[(x+tx*u-ty*v,y+ty*u+tx*v) for u,v in corners]
                msp.add_lwpolyline(xy,close=True,dxfattribs={'layer':layer})
            rectangle(FOUNDATION_LAYER,settings.foundation_width,settings.foundation_length)
            rectangle(COPING_LAYER,settings.coping_width,settings.coping_length)
            msp.add_circle((x,y),settings.column_diameter/2,dxfattribs={'layer':COLUMN_LAYER})
            for k in counts:counts[k]+=1
    return counts
