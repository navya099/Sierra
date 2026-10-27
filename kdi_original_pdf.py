"""U16-R6: original KDI III-117 2-page form; fill A cost and F provisional total.

The original table geometry is preserved as a PDF template, not re-typeset.
No changes to cost calculations or the XLSX summary. Requires PyMuPDF.
"""
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import fitz

TEMPLATE = Path(__file__).with_name('kdi_iii117_original_2pages.pdf')
MILLION = Decimal('1000000')

# Positions are measured on the actual KDI original, PDF page coordinates in points.
# Keys are canonical cost categories; values are (page index, row center Y).
ROWS = {
 'earth_general':(0,377), 'earth_soft':(0,389), 'earth_other':(0,401),
 'bridge_direct':(0,413), 'bridge_pile':(0,425), 'bridge_other':(0,437),
 'tunnel_main':(0,449), 'tunnel_long':(0,461), 'tunnel_slope':(0,476), 'tunnel_safety':(0,491), 'tunnel_other':(0,505),
 'cross_road':(0,517), 'cross_under':(0,529), 'cross_walk':(0,541), 'cross_other':(0,553),
 'station_earth_0':(0,577),'station_earth_1':(0,589),'station_earth_2':(0,601),'station_earth_other':(0,613),
 'station_bridge_0':(0,625),'station_bridge_1':(0,637),'station_bridge_2':(0,649),'station_bridge_other':(0,661),
 'station_under_0':(0,673),'station_under_1':(0,685),'station_under_other':(0,697),
 'track':(0,709),
 'arch_over_mid':(1,223),'arch_over_branch':(1,235),'arch_over_terminal':(1,247),
 'arch_ground_mid':(1,259),'arch_ground_branch':(1,271),'arch_ground_terminal':(1,283),
 'arch_below_mid':(1,296),'arch_below_branch':(1,308),'arch_underground':(1,320),'arch_other':(1,332),
 'trans':(1,357),'substation':(1,369),
 'cat_earth':(1,381),'cat_bridge':(1,393),'cat_tunnel':(1,405),'cat_rigid':(1,418),
 'power_earth':(1,430),'power_bridge':(1,442),'power_tunnel':(1,454),
 'signal':(1,467),'comm':(1,479),'depot':(1,491),
}

def classify(row):
    sec=str(row['section']);code=str(row.get('code','')).upper();name=str(row.get('name',''))
    sub=str(row.get('sub',''))
    if sec=='노반 본선':
        if 'EARTH' in code or '토공' in sub:
            return 'earth_soft' if 'SOFT' in code else ('earth_general' if 'GENERAL' in code else 'earth_other')
        if 'BRIDGE' in code or '교량' in sub:
            return 'bridge_direct' if 'DIRECT' in code else ('bridge_pile' if 'PILE' in code else 'bridge_other')
        if 'TUNNEL' in code or '터널' in sub:
            return 'tunnel_long' if 'LONG' in code else 'tunnel_main'
        if 'CROSS' in code or '입체' in sub:
            return 'cross_road' if 'ROAD' in code else 'cross_other'
    if sec=='노반 정거장':
        typ='under' if any(x in code for x in ('UNDER','CUT','UG')) else ('bridge' if 'BRIDGE' in code else 'earth')
        return 'station_'+typ+'_other'  # preserve all uncertain station specs in 기타
    if sec=='궤도':return 'track'
    if sec=='송전선로':return 'trans'
    if sec=='변전설비':return 'substation'
    if sec=='전차선':
        if 'RIGID' in code:return 'cat_rigid'
        if 'BRIDGE' in code:return 'cat_bridge'
        if 'TUNNEL' in code:return 'cat_tunnel'
        return 'cat_earth'
    if sec=='전력':
        if 'BRIDGE' in code:return 'power_bridge'
        if 'TUN' in code:return 'power_tunnel'
        return 'power_earth'
    if sec=='신호':return 'signal'
    if sec=='통신':return 'comm'
    if sec=='건축':
        pos='underground' if '_UNDER_' in code else ('below' if '_BELOW_' in code else ('ground' if '_GROUND_' in code else ('over' if '_OVER_' in code else 'other')))
        if pos=='underground':return 'arch_underground'
        if pos=='other':return 'arch_other'
        kind='terminal' if 'TERMINAL' in code else ('branch' if 'BRANCH' in code else 'mid')
        return 'arch_'+pos+'_'+kind
    if sec=='기계설비':
        # Original KDI III-117 has no dedicated mechanical-services row.
        return None
    return None

def export_original_pdf(path,ledger,*,line_km=None,station_count=None,bridge_count=None,tunnel_count=None,bridge_length_m=None,tunnel_length_m=None,existing_km=None,new_km=None):
    if not TEMPLATE.exists():raise FileNotFoundError(f'KDI 원문 템플릿 없음: {TEMPLATE}')
    grouped=defaultdict(list)
    total=Decimal(0)
    for row in ledger:
        amount=Decimal(str(row['amount']));total+=amount
        key=classify(row)
        if key is None or key not in ROWS:
            if amount!=0:raise ValueError(f'KDI 원문 대응 행 없음: {row["section"]} / {row["code"]}')
            continue
        grouped[key].append(row)
    pdf=fitz.open(TEMPLATE)
    def draw(page,x,y,value,width,fontsize=7.1):
        if value is None or value=='':return
        txt=str(value)
        # fit numeric text to narrow original cells
        fs=fontsize
        while fitz.get_text_length(txt,fontname='helv',fontsize=fs)>width and fs>5.1:fs-=.2
        page.insert_text((x,y+2.2),txt,fontsize=fs,fontname='helv',color=(0,0,0),overlay=True)
    def fmt(v,precision=3):
        v=Decimal(str(v));return f'{v:,.{precision}f}'.rstrip('0').rstrip('.') if v else '0'
    def write_row(key,items):
        page_index,y=ROWS[key];p=pdf[page_index]
        amt=sum((Decimal(str(r['amount'])) for r in items),Decimal(0))
        # HF2: hide zero-priced lines in PDF only; preserve ledger and totals.
        if items and all(Decimal(str(r["unit_price"])) == 0 for r in items):
            return
        # A single source item retains quantity and rate; multiple items show amount only.
        if len(items)==1:
            r=items[0];draw(p,340,y,fmt(r['quantity'],3),29,6.5)
            draw(p,373,y,fmt(Decimal(str(r['unit_price']))/MILLION,3),36,6.5)
        draw(p,413,y,fmt(amt/MILLION,3),38,6.4)
    for key,items in grouped.items():write_row(key,items)
    # Original A. 공사비 heading and F. 총사업비 row. F is a provisional copy of A.
    draw(pdf[0],413,353,fmt(total/MILLION),38,6.4)
    draw(pdf[1],413,710,fmt(total/MILLION),38,6.4)
    # The original F cell has a narrow note field; use a short marker.
    draw(pdf[1],455,710,'*',18,7)
    draw(pdf[1],128,734,'* F = A (provisional; B-E not estimated)',280,7)
    # Short explanatory note below the original table; do not alter B-E blank cells.
    # Draw only in whitespace; preserve original page number and continuing-table caption.
    # HF3: total, existing-line, and new-line fields in the original KDI header.
    if line_km is not None: draw(pdf[0],157,287,fmt(line_km,3),31,9.0)
    if existing_km is not None: draw(pdf[0],242,287,fmt(existing_km,3),31,9.0)
    if new_km is not None: draw(pdf[0],312,287,fmt(new_km,3),29,9.0)
    if station_count is not None: draw(pdf[0],163,297,str(station_count),15,9.0)
    if bridge_count is not None: draw(pdf[0],183,307,str(bridge_count),15,9.0)
    if tunnel_count is not None: draw(pdf[0],285,307,str(tunnel_count),15,9.0)
    if bridge_length_m is not None: draw(pdf[0],221,307,fmt(bridge_length_m,0),39,8.4)
    if tunnel_length_m is not None: draw(pdf[0],323,307,fmt(tunnel_length_m,0),57,8.4)
    # F provisional status is also carried in PDF metadata, for downstream inspection.
    pdf.set_metadata({'title':'KDI 표 Ⅲ-117 총사업비 내역 (개략적 기준)',
                      'subject':'F 총사업비는 A 공사비 산정분을 임시 반영; B-E 미산정'})
    pdf.save(str(path),garbage=4,deflate=True)
    pdf.close()
    return total
