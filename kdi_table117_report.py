"""U16-R1: KDI III-117 construction-cost report; estimator remains untouched."""
from collections import defaultdict
from decimal import Decimal
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

SPECS = {
 '노반 본선': {'토공':['일반구간','연약구간','기타'], '교량':['직접기초','말뚝기초','기타'], '터널':['본선','초장대 본선','경사갱','방재설비','기타'], '입체교차':['과선도로교','지하차도','보도육교','기타']},
 '노반 정거장': {'토공':['1홈 2선','2홈 2선','2홈 4선','기타'], '교량':['1홈 2선','2홈 2선','2홈 4선','기타'], '지하':['개착 2층','개착 3층','기타']},
}
SYSTEM_SECTIONS=['궤도','전차선','전력','송전선로','변전설비','신호','통신','건축','기계설비']
SHEET='KDI_III-117_공사비'

def dec(v):
 x=Decimal(str(v))
 if not x.is_finite() or x<0: raise ValueError('공사비 수량/금액이 올바르지 않습니다')
 return x

def station_kind(code):
 code=code.upper()
 if '_EARTH_' in code:return '토공'
 if '_BRIDGE_' in code:return '교량'
 if any(x in code for x in ('_UNDER_','_CUT_','_UG_')):return '지하'
 return '기타'

def station_spec(code):
 for token,label in [('P12','1홈 2선'),('P22','2홈 2선'),('P24','2홈 4선')]:
  if '_'+token+'_' in code.upper():return label
 return '기타'

def add_table117(wb, road_rows, station_records, system_records):
 if SHEET in wb:del wb[SHEET]
 ws=wb.create_sheet(SHEET,0);ws.sheet_view.showGridLines=False
 ws.merge_cells('A1:G1');ws['A1']='표 Ⅲ-117 총사업비 내역 (일반철도: 개략적 기준) — 공사비'
 ws['A1'].font=Font(name='맑은 고딕',size=15,bold=True,color='FFFFFF');ws['A1'].fill=PatternFill('solid',fgColor='17365D')
 ws['A2']='가격 기준';ws['B2']='2019년';ws['D2']='단위';ws['E2']='백만원';ws['G2']='미산정은 공란, 실제 산정 0원은 0으로 표시'
 ws.append(['공종','규격','단위','수량','단가(백만원)','금액(백만원)','비고'])
 for c in ws[3]:c.font=Font(name='맑은 고딕',bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='366092');c.alignment=Alignment(horizontal='center')
 records=[]
 for r in road_rows:
  group=str(r.group);description=str(r.description)
  spec='기타'
  for label in SPECS['노반 본선'].get(group,[]):
   if label!='기타' and label.replace(' ','') in description.replace(' ',''):spec=label;break
  records.append(('노반 본선',group,spec,description,str(r.unit),r.quantity,r.unit_price,r.amount,str(r.code)))
 for r in station_records:
  code=str(r['code']);kind=station_kind(code);spec=station_spec(code) if kind!='지하' else '기타'
  records.append(('노반 정거장',kind,spec,str(r['name']),'개소',r['quantity'],r['unit_price'],r['amount'],code))
 for r in system_records:
  group=str(r['group']);records.append((group,'','',str(r['name']),str(r['unit']),r['quantity'],r['unit_price'],r['amount'],str(r['code'])))
 buckets=defaultdict(list)
 for rec in records:buckets[rec[0]].append(rec)
 total=Decimal(0);section_sums={};detail_sum=Decimal(0)
 def row(values,style=None):
  ws.append(values);n=ws.max_row
  if style:
   color='DCE6F1' if style=='section' else 'EAF0F6' if style=='sub' else 'C9DAE9'
   for cell in ws[n]:cell.fill=PatternFill('solid',fgColor=color);cell.font=Font(name='맑은 고딕',bold=True,color='17365D')
  for j in (4,5,6):ws.cell(n,j).number_format='#,##0.######'
  ws.cell(n,7).alignment=Alignment(wrap_text=True,vertical='center')
  return n
 def detail(rec):
  nonlocal total,detail_sum
  sec,sub,spec,name,unit,qty,price,amount,code=rec
  qty=dec(qty);price=dec(price);amount=dec(amount)
  total+=amount;detail_sum+=amount
  row(['',name,unit,float(qty),float(price/1000000),float(amount/1000000),code])
 def subtotal(label,amount):row([label,'소계',None,None,None,float(amount/1000000),None],'sub')
 for section in ['노반 본선','노반 정거장']+SYSTEM_SECTIONS:
  data=buckets.pop(section,[]);section_total=sum((dec(r[7]) for r in data),Decimal(0))
  section_sums[section]=section_total
  row([section,None,None,None,None,None,'미산정 규격은 공란'],'section')
  if section in SPECS:
   consumed=set()
   for sub,specs in SPECS[section].items():
    row(['',sub,None,None,None,None,None],'sub')
    for spec in specs:
     matching=[(i,r) for i,r in enumerate(data) if i not in consumed and r[1]==sub and r[2]==spec]
     if not matching:row(['',spec,None,None,None,None,None])
     for i,r in matching:detail(r);consumed.add(i)
    subtotal(sub,sum((dec(r[7]) for r in data if r[1]==sub),Decimal(0)))
   remaining=[r for i,r in enumerate(data) if i not in consumed]
   if remaining:
    row(['','기타/미분류',None,None,None,None,'원문 세부 항목 매핑 확인 필요'],'sub')
    for r in remaining:detail(r)
  else:
   for r in data:detail(r)
  subtotal(section,section_total)
 for section,data in buckets.items():
  section_total=sum((dec(r[7]) for r in data),Decimal(0))
  row([section,None,None,None,None,None,'원문 항목 외 공종: 누락 방지'],'section')
  for r in data:detail(r)
  subtotal(section,section_total)
 assert total==detail_sum,'세부 금액 합계 불일치'
 assert total==sum((dec(r[7]) for r in records),Decimal(0)),'원본 공사비와 불일치'
 row(['공사비 산정분 합계',None,None,None,None,float(total/1000000),'미산정 항목 제외 · 전체 사업비 아님'],'total')
 ws.append(['주','KDI 표 Ⅲ-117 참조',None,None,None,None,'상세 규격 매핑은 코드·설명 기준이며 원문 세부 분류는 검토 필요.'])
 for col,width in {'A':24,'B':44,'C':14,'D':15,'E':21,'F':23,'G':70}.items():ws.column_dimensions[col].width=width
 ws.freeze_panes='D4';ws.sheet_properties.pageSetUpPr.fitToPage=True
 ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A3;ws.page_setup.fitToWidth=1
 ws.print_title_rows='1:3';ws.print_options.horizontalCentered=True
 return ws
