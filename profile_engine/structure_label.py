"""v12.5.3 common structure location label, in output drawing coordinates."""
from dataclasses import dataclass
import math
import ezdxf
from ezdxf.enums import TextEntityAlignment

@dataclass(frozen=True)
class LabelSettings:
    station_prefix: str = 'STA.'  # user-defined railway stationing prefix
    text_height: float = 3.0
    color: int = 1
    line_margin: float = 3.0
    bridge_type: str = 'PSC'
    def validate(self):
        if not self.station_prefix.strip() or any(ch in self.station_prefix for ch in '\r\n\t') or len(self.station_prefix) > 30:
            raise ValueError('측점 접두어는 1~30자이며 줄바꿈이나 탭을 포함할 수 없습니다.')
        if not all(math.isfinite(v) and v > 0 for v in (self.text_height, self.line_margin)):
            raise ValueError('문자 높이와 사선 여유는 양수여야 합니다.')
        if type(self.color) is not int or not 1 <= self.color <= 255:
            raise ValueError('주석 색상은 ACI 1~255이어야 합니다.')
        if not self.bridge_type.strip():
            raise ValueError('교량 형식은 비워둘 수 없습니다.')

def station_text(sta):
    sign = '-' if sta < 0 else ''
    hundredths = int(math.floor(abs(sta)*100 + 0.5))
    km, rem = divmod(hundredths, 100000)
    return f'{sign}{km}km{rem/100:06.2f}'

def label_lines(structure, settings):
    kind = structure.kind
    if kind not in ('BRIDGE','TUNNEL'):
        return None
    name = structure.name.strip() or ('교량' if kind == 'BRIDGE' else '터널')
    # The bridge type is global until a per-structure type is introduced.
    title = f'B.({settings.bridge_type.strip()}) {name}' if kind == 'BRIDGE' else f'T. {name}'
    subtitle = f'{settings.station_prefix} {station_text(structure.start_sta)} L={structure.length:,.2f}'
    return title, subtitle

def _width_estimate(text, height):
    # Korean/CJK glyphs occupy approximately a full em, Latin roughly 0.65 em.
    # Conservative width estimate: actual CAD font metrics are font dependent.
    import unicodedata
    return sum(height*(1.0 if unicodedata.east_asian_width(ch) in ('F','W') else 0.65) for ch in text)

def draw_structure_labels(msp, structures, settings, sheet_start, sheet_end,
                          datum_segments, elevation_at, display_sta, display_el,
                          layer='STRUCTURE_LABEL'):
    settings.validate()
    if layer not in msp.doc.layers:
        msp.doc.layers.new(layer, dxfattribs={'color':settings.color,'lineweight':18})
    else:
        msp.doc.layers.get(layer).dxf.color=settings.color
    count=0
    angle=math.radians(30)
    ux,uy=math.cos(angle),math.sin(angle)
    for structure in structures or ():
        lines=label_lines(structure,settings)
        if lines is None: continue
        sta=structure.start_sta
        # Exactly one owner sheet: the sheet beginning at a split boundary.
        if not (sheet_start-1e-7 <= sta < sheet_end-1e-7):
            if not (abs(sta-sheet_end)<1e-7 and abs(sheet_end-sheet_start)<1e-7):
                continue
        datum=next((seg for seg in datum_segments if seg.start_sta-1e-7 <= sta+1e-6 <= seg.end_sta+1e-7),None)
        if datum is None: continue
        x0=display_sta(sta); y0=display_el(elevation_at(sta),datum.datum_el)
        x1,y1=x0,y0+30.0
        length=max(_width_estimate(t,settings.text_height) for t in lines)+settings.line_margin
        x2,y2=x1+length*ux,y1+length*uy
        msp.add_line((x0,y0),(x1,y1),dxfattribs={'layer':layer})
        msp.add_line((x1,y1),(x2,y2),dxfattribs={'layer':layer})
        # TEXT insertion locations parallel to the sloped guide, offset along normal.
        for text,offset in ((lines[0],settings.text_height*0.55),(lines[1],-settings.text_height*1.20)):
            tx=x1-uy*offset;ty=y1+ux*offset
            ent=msp.add_text(text,dxfattribs={'layer':layer,'style':'KOREAN','height':settings.text_height,'rotation':30})
            ent.set_placement((tx,ty),align=TextEntityAlignment.LEFT)
        count+=1
    return count
