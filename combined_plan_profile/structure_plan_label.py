"""Plan-only structure labels, using the existing v12.5.3 label_lines engine."""
from dataclasses import dataclass
import math
from ezdxf.enums import TextEntityAlignment
from .profile_engine.structure_label import label_lines, LabelSettings, station_text

@dataclass(frozen=True)
class PlanLabelSettings:
    offset: float = 15.0   # signed metres; positive = left of alignment
    height: float = 3.0
    layer: str = 'STRUCTURE_LABEL_PLAN'
    color: int = 1

    def validate(self):
        if not math.isfinite(self.offset): raise ValueError('평면 레이블 이격거리는 유한한 값이어야 합니다.')
        if not math.isfinite(self.height) or self.height <= 0: raise ValueError('평면 레이블 문자 높이는 양수여야 합니다.')
        if not self.layer.strip() or any(c in self.layer for c in '<>/\\":;?*|=,') or len(self.layer)>255:
            raise ValueError('평면 레이블 레이어 이름이 유효하지 않습니다.')
        if type(self.color) is not int or not 1<=self.color<=255: raise ValueError('평면 레이블 색상은 ACI 1~255입니다.')

def draw_plan_structure_labels(msp,structures,settings,label_settings,*,points,distances,position_at,station_origin=0.0):
    settings.validate()
    label_settings.validate()
    if settings.layer not in msp.doc.layers:
        msp.doc.layers.new(settings.layer,dxfattribs={'color':settings.color})
    else:
        msp.doc.layers.get(settings.layer).dxf.color=settings.color
    if 'KOREAN' not in msp.doc.styles:
        msp.doc.styles.new('KOREAN',dxfattribs={'font':'txt.shx'})
    count=0
    for st in structures or ():
        lines=label_lines(st,label_settings)
        if lines is None: continue
        # E.1.3: label only at the START station; no end-station text.
        for endpoint in (st.start_sta,):
            local=endpoint-station_origin
            if local < -1e-6 or local > distances[-1]+1e-6: continue
            (x,y),(tx,ty)=position_at(local,points,distances)
            length=math.hypot(tx,ty)
            if length<1e-12: continue
            tx/=length;ty/=length
            nx,ny=-ty,tx
            x+=nx*settings.offset;y+=ny*settings.offset
            # Retain common name/length formatter; update station for each end.
            endpoint_lines=(lines[0], f'{label_settings.station_prefix} {station_text(endpoint)} L={st.length:,.2f}')
            # Both TEXT lines share the same tangent-direction start anchor.
            # The station line is below the title in the text-local normal
            # direction; no leader lines or end-station labels.
            rotation=math.degrees(math.atan2(ty,tx))
            for line,normal_offset in ((endpoint_lines[0], 0.0),
                                       (endpoint_lines[1], -settings.height*1.6)):
                px=x+nx*normal_offset
                py=y+ny*normal_offset
                entity=msp.add_text(line,dxfattribs={
                    'layer':settings.layer,'height':settings.height,
                    'style':'KOREAN','rotation':rotation})
                entity.set_placement((px,py),align=TextEntityAlignment.LEFT)
            count+=1
    return count
