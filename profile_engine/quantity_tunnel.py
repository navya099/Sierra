"""Tunnel body preliminary quantities from actual DXF closed polylines (mm)."""
from dataclasses import dataclass
import math
import ezdxf

@dataclass(frozen=True)
class TunnelQuantity:
    name: str
    start_sta: float
    end_sta: float
    length_m: float
    outer_area_m2: float
    inner_area_m2: float
    lining_area_m2: float
    excavation_m3: float
    lining_m3: float
    inner_space_m3: float
    source: str

def _signed_poly_area(ent):
    """Exact signed area: shoelace chords + circular bulge segments."""
    pts=list(ent.get_points('xyb'))
    if not ent.closed or len(pts)<3: raise ValueError('폐합 LWPOLYLINE이 필요합니다.')
    area=0.0
    for i,(x,y,b) in enumerate(pts):
        x2,y2,_=pts[(i+1)%len(pts)]
        area+=(x*y2-x2*y)/2
        if b:
            chord=math.hypot(x2-x,y2-y)
            if chord==0:raise ValueError('곡선 세그먼트 길이가 0입니다.')
            theta=4*math.atan(b)
            # stable formula using chord and bulge (avoids radius overflow near zero)
            radius=chord*(1+b*b)/(4*abs(b))
            area+=radius*radius*(theta-math.sin(theta))/2
    if not math.isfinite(area):raise ValueError('단면 면적이 유효하지 않습니다.')
    return area

def read_tunnel_areas(dxf_path):
    doc=ezdxf.readfile(str(dxf_path))
    entities={}
    for layer in ('TUNNEL_OUTER','TUNNEL_INNER'):
        found=[e for e in doc.modelspace() if e.dxf.layer.upper()==layer]
        if len(found)!=1 or found[0].dxftype()!='LWPOLYLINE' or not found[0].closed:
            raise ValueError(f'{layer}: 폐합 LWPOLYLINE 정확히 1개가 필요합니다.')
        entities[layer]=found[0]
    # Reuse established tunnel-section geometric validation.
    from tunnel_section import load_tunnel_section
    load_tunnel_section(dxf_path)
    outer=abs(_signed_poly_area(entities['TUNNEL_OUTER']))*1e-6
    inner=abs(_signed_poly_area(entities['TUNNEL_INNER']))*1e-6
    if outer<=inner or inner<=0:
        raise ValueError('외곽 면적은 내공 면적보다 커야 합니다.')
    return outer,inner

def calculate_tunnel_quantities(segments,section_dxf):
    if not section_dxf:raise ValueError('터널 수량산출에는 사용자 단면 DXF가 필요합니다. 터널 설정에서 DXF를 선택하세요.')
    outer,inner=read_tunnel_areas(section_dxf)
    result=[]
    for s in segments:
        if s.kind!='TUNNEL':continue
        length=s.end_sta-s.start_sta
        if not math.isfinite(length) or length<=0:raise ValueError(f'{s.name}: 터널 연장이 유효하지 않습니다.')
        result.append(TunnelQuantity(s.name,s.start_sta,s.end_sta,length,outer,inner,outer-inner,
                    outer*length,(outer-inner)*length,inner*length,s.source))
    return result

def export_tunnel_xlsx(rows,path,section_dxf):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb=Workbook(); ws=wb.active; ws.title='터널별 수량'
    ws.append(['터널명','시점 STA(m)','종점 STA(m)','연장(m)','굴착 단면적(m²)',
               '내공 단면적(m²)','라이닝 단면적(m²)','굴착 체적(m³)',
               '라이닝 체적(m³)','내공 체적(m³)','출처'])
    for r in rows:
        ws.append([r.name,r.start_sta,r.end_sta,r.length_m,r.outer_area_m2,r.inner_area_m2,
                   r.lining_area_m2,r.excavation_m3,r.lining_m3,r.inner_space_m3,r.source])
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    for row in ws.iter_rows(min_row=2):
        for c in row[1:10]:c.number_format='#,##0.000'
    for i in range(1,12):ws.column_dimensions[get_column_letter(i)].width=22
    sm=wb.create_sheet('집계 및 산출기준')
    sm.append(['항목','수량','단위'])
    for label,val,unit in [('터널 개소',len(rows),'EA'),('총연장',sum(r.length_m for r in rows),'m'),
        ('굴착 체적',sum(r.excavation_m3 for r in rows),'m³'),
        ('라이닝 체적',sum(r.lining_m3 for r in rows),'m³'),
        ('내공 체적',sum(r.inner_space_m3 for r in rows),'m³')]:sm.append([label,val,unit])
    sm.append(['단면 DXF',str(section_dxf),''])
    sm.append(['산출 방법','폐합 LWPOLYLINE 실제 면적 × 터널 연장',''])
    sm.append(['단위','DXF mm → m² (1e-6)',''])
    sm.append(['제외','갱구부, 확폭, 여굴, 배수/인버트 세부, 부속시설',''])
    sm.append(['주의','동일 단면을 모든 터널에 적용한 개략 수량',''])
    for col,width in [('A',24),('B',65),('C',15)]:sm.column_dimensions[col].width=width
    for sheet in (ws,sm):
        for cell in sheet[1]:
            cell.fill=PatternFill('solid',fgColor='17365D')
            cell.font=Font(bold=True,color='FFFFFF')
        sheet.row_dimensions[1].height=25
    wb.save(str(path))
