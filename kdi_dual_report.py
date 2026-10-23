"""U16-R3: one normalized cost ledger; XLSX review summary and submission PDF."""
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

SECTIONS = ['노반 본선','노반 정거장','궤도','전차선','전력','송전선로','변전설비','신호','통신','건축','기계설비']

def _d(value):
    d=Decimal(str(value))
    if not d.is_finite() or d<0: raise ValueError('공사비 금액/수량 오류')
    return d

def build_ledger(road_rows, station_records, system_records):
    ledger=[]
    for r in road_rows:
        ledger.append(dict(section='노반 본선',sub=str(r.group),name=str(r.description),code=str(r.code),unit=str(r.unit),quantity=_d(r.quantity),unit_price=_d(r.unit_price),amount=_d(r.amount)))
    for r in station_records:
        ledger.append(dict(section='노반 정거장',sub='정거장',name=str(r['name']),code=str(r['code']),unit='개소',quantity=_d(r['quantity']),unit_price=_d(r['unit_price']),amount=_d(r['amount'])))
    for r in system_records:
        ledger.append(dict(section=str(r['group']),sub='',name=str(r['name']),code=str(r['code']),unit=str(r['unit']),quantity=_d(r['quantity']),unit_price=_d(r['unit_price']),amount=_d(r['amount'])))
    return ledger

def add_review_sheet(wb, ledger):
    from openpyxl.styles import Font, PatternFill, Alignment
    name='통합공사비집계'
    if name in wb: del wb[name]
    ws=wb.create_sheet(name,0)
    ws.append(['통합 개략공사비 집계 · KDI 2019년 기준 · 산정분만 표시'])
    ws.merge_cells('A1:G1')
    ws.append(['공종','세부공종','산정항목 / 단가코드','단위','수량','단가(원)','금액(원)'])
    totals=defaultdict(lambda:Decimal(0))
    for r in ledger:
        ws.append([r['section'],r['sub'],r['name']+' / '+r['code'],r['unit'],float(r['quantity']),float(r['unit_price']),float(r['amount'])])
        totals[r['section']]+=r['amount']
    ws.append(['공종별 소계'])
    for sec in SECTIONS+sorted(set(totals)-set(SECTIONS)):
        if sec in totals: ws.append([sec,'소계',None,None,None,None,float(totals[sec])])
    grand=sum(totals.values(),Decimal(0))
    ws.append(['전체 산정분 합계',None,None,None,None,None,float(grand)])
    ws.append(['※ 미산정 공종은 집계에서 제외하며, 실제 산정 0원은 그대로 표시합니다. 전체 사업비가 아닌 산정분 합계입니다.'])
    ws.merge_cells(start_row=ws.max_row,start_column=1,end_row=ws.max_row,end_column=7)
    for row in ws:
        for c in row:
            c.font=Font(name='맑은 고딕',size=10,bold=(c.row<=2 or c.column==1 and ('소계' in str(ws.cell(c.row,2).value) or '합계' in str(c.value))))
            if c.row<=2: c.fill=PatternFill('solid',fgColor='DCE8F5')
            if c.column in (5,6,7):c.number_format='#,##0.######'
            c.alignment=Alignment(vertical='center')
    for col,width in {'A':20,'B':18,'C':64,'D':12,'E':14,'F':20,'G':22}.items():ws.column_dimensions[col].width=width
    ws.freeze_panes='D3';ws.sheet_view.showGridLines=False
    ws.auto_filter.ref=f'A2:G{2+len(ledger)}'
    return grand

def export_pdf(path, ledger, *, line_km=None, station_count=None):
    """U16-R4: grouped KDI submission PDF. No changes to ledger or XLSX."""
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from xml.sax.saxutils import escape
    import os

    fonts=[r'C:\Windows\Fonts\malgun.ttf',r'C:\Windows\Fonts\gulim.ttc',
           '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
           '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    font=next((f for f in fonts if os.path.isfile(f)),None)
    if not font: raise RuntimeError('PDF 출력용 한글 글꼴을 찾을 수 없습니다.')
    pdfmetrics.registerFont(TTFont('KDIReportKorean',font))
    small=ParagraphStyle('r4small',fontName='KDIReportKorean',fontSize=7.1,leading=10)
    normal=ParagraphStyle('r4normal',parent=small,fontSize=8,leading=11)
    title=ParagraphStyle('r4title',parent=normal,fontSize=14,leading=20,alignment=1,spaceAfter=9)
    P=lambda v,style=small:Paragraph(escape(str(v)),style)
    def num(v,places=3):
        # Round only for presentation; Decimal ledger stays unchanged.
        return f'{v:,.{places}f}'.rstrip('0').rstrip('.') if v else '0'
    page=landscape(A4)
    doc=SimpleDocTemplate(str(path),pagesize=page,leftMargin=30,rightMargin=30,
                          topMargin=33,bottomMargin=34,title='KDI 표 Ⅲ-117 공사비 내역')
    story=[P('표 Ⅲ-117  총사업비 내역 (일반철도: 개략적 기준)',title)]
    overview='가격 기준: 2019년  |  금액 단위: 백만원  |  공사비 산정분 (미산정 제외)'
    if line_km is not None: overview+=f'  |  총연장: {line_km:.3f} km'
    if station_count is not None: overview+=f'  |  정거장: {station_count}개소'
    story.extend([P(overview,normal),Spacer(1,9)])
    widths=[91,228,46,62,86,95,167]
    header=['공종','규격 / 산정항목','단위','수량','단가(백만원)','금액(백만원)','비고']
    line=colors.HexColor('#8392A0')
    def styled(rows, bands=(), subtotal_index=None, header_row=False):
        t=Table(rows,colWidths=widths,hAlign='CENTER',repeatRows=1 if header_row else 0)
        st=[('GRID',(0,0),(-1,-1),.35,line),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]
        for i in bands:
            st.extend([('BACKGROUND',(0,i),(-1,i),colors.HexColor('#E9EFF5')),
                       ('SPAN',(0,i),(5,i))])
        if subtotal_index is not None:
            st.extend([('BACKGROUND',(0,subtotal_index),(-1,subtotal_index),colors.HexColor('#F1F4F7')),
                       ('SPAN',(0,subtotal_index),(4,subtotal_index))])
        if header_row: st.append(('BACKGROUND',(0,0),(-1,0),colors.HexColor('#D9E3ED')))
        t.setStyle(TableStyle(st))
        return t
    story.append(styled([[P(h,normal) for h in header]],header_row=True))
    by=defaultdict(list)
    for r in ledger: by[r['section']].append(r)
    total=Decimal(0)
    for sec in SECTIONS+sorted(set(by)-set(SECTIONS)):
        entries=by.get(sec,[])
        rows=[[P(sec,normal),'','','','','',P('미산정' if not entries else '')]]
        for r in entries:
            rows.append(['',P((r['sub']+' · ' if r['sub'] else '')+r['name']),P(r['unit']),
                         P(num(r['quantity'],4)),P(num(r['unit_price']/1000000)),
                         P(num(r['amount']/1000000)),P(r['code'])])
        subtotal=sum((r['amount'] for r in entries),Decimal(0));total+=subtotal
        rows.append([P(sec+' 소계',normal),'','','','',
                     P(num(subtotal/1000000) if entries else ''),''])
        block=styled(rows,bands=(0,),subtotal_index=len(rows)-1)
        # Keep the whole short section together; longer sections may split naturally.
        if len(rows)<=12: story.append(KeepTogether([block]))
        else: story.append(block)
    grand=[[P('공사비 산정분 합계',normal),'','','','',P(num(total/1000000)),P('미산정 제외')]]
    gt=styled(grand)
    gt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#D9E3ED')),
                            ('SPAN',(0,0),(4,0))]))
    story.append(KeepTogether([gt,Spacer(1,7),P('주: 실제 산정 0원은 0으로 표시하며, 미산정 항목은 공란으로 표시합니다. 전체 사업비가 아닌 산정된 공사비만 포함합니다.',normal)]))
    def footer(canvas,doc):
        canvas.setFont('KDIReportKorean',8)
        canvas.drawRightString(page[0]-30,19,f'{doc.page} 쪽')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return total
