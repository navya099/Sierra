"""P1: audited estimated-portion aggregation. No unestimated cost is treated as zero."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
from dataclasses import dataclass
from nonconstruction_cost import load_json, CATEGORIES

WORKS=('토공','교량','터널')
MISSING=('궤도','전력·전차선','신호','통신','건축','기계설비','기타 미산정 공사')

@dataclass(frozen=True)
class ProjectCost:
    construction:tuple
    other:tuple
    missing:tuple
    construction_file:str
    other_file:str
    notes:tuple
    @property
    def subtotal(self):return sum((v for _,v in self.construction+self.other),Decimal(0))

def money(v):
    try: d=Decimal(str(v))
    except (InvalidOperation,ValueError,TypeError):raise ValueError('유효하지 않은 금액') from None
    if not d.is_finite() or d<0 or d!=d.to_integral_value():raise ValueError('금액은 음수가 아닌 정수 원이어야 합니다.')
    return d

def read_construction(path):
    from openpyxl import load_workbook
    wb=load_workbook(path,read_only=True,data_only=True)
    try:
        if '통합공사비총괄' not in wb.sheetnames or '통합공사비내역' not in wb.sheetnames:
            raise ValueError('D5 통합 공사비 파일이 아닙니다.')
        ws=wb['통합공사비총괄']; rows=list(ws.values)
        if not rows or tuple(rows[0][:4])!=('공종','선택방식','산정금액(원)','상태'):
            raise ValueError('D5 총괄 시트 열 구성이 다릅니다.')
        if len(rows)!=5 or tuple(r[0] for r in rows[1:])!=WORKS+('산정분 합계',):
            raise ValueError('D5 총괄 시트 공종 구성이 다릅니다.')
        details=list(wb['통합공사비내역'].values)
        if not details or tuple(details[0][:8])!=('공종','산정방식','단가코드','적용조건','수량','단위','적용단가(원)','금액(원)'):
            raise ValueError('D5 내역 시트 열 구성이 다릅니다.')
        sums={k:Decimal(0) for k in WORKS}; counts={k:0 for k in WORKS}
        for row in details[1:]:
            if not row or not row[0]:continue
            g,mode=row[:2]
            if g not in WORKS or mode not in ('ROUGH','DETAIL'):
                raise ValueError('D5 내역의 공종/방식 오류')
            q=Decimal(str(row[4])); price=Decimal(str(row[6])); amt=Decimal(str(row[7]))
            if not all(v.is_finite() and v>=0 for v in (q,price,amt)) or q<=0 or abs(q*price-amt)>max(Decimal('.02'),amt*Decimal('0.000000001')):
                raise ValueError('D5 내역 수량·단가·금액 불일치')
            sums[g]+=amt;counts[g]+=1
        out=[];missing=[]
        for row in rows[1:4]:
            g,mode,value,state=row[:4]
            if mode not in ('ROUGH','DETAIL','NONE'):raise ValueError(f'{g}: 방식 오류')
            if mode=='NONE':
                if counts[g] or money(value)!=0 or state!='미산정':raise ValueError(f'{g}: 미산정 상태 불일치')
                missing.append(g)
            else:
                if not counts[g] or state!='산정' or any(r[0]==g and r[1]!=mode for r in details[1:] if r[0]):
                    raise ValueError(f'{g}: 산정방식과 내역 불일치')
                if abs(Decimal(str(value))-sums[g])>Decimal('.02'):raise ValueError(f'{g}: 총괄·내역 금액 불일치')
                out.append((g,money(round(sums[g]))))
        if abs(Decimal(str(rows[4][2]))-sum(sums.values()))>Decimal('.02'):
            raise ValueError('D5 총괄 합계가 상세내역과 다릅니다.')
        return tuple(out),tuple(missing)
    finally:wb.close()

def aggregate(construction_path, other_path):
    cp=Path(construction_path);op=Path(other_path)
    if not cp.is_file() or not op.is_file():raise ValueError('원본 파일을 모두 선택하세요.')
    construction,missing=read_construction(cp)
    items=load_json(op)
    other=tuple((c,sum((i.amount for i in items if i.category==c),Decimal(0))) for c in CATEGORIES)
    notes=('노반 공사비는 D5에서 선택된 산정분만 포함',
           '공사비 외 비용은 T1/T2 JSON의 사용자 입력 금액 그대로 합산',
           '예비비 등 요율 산정 기준금액의 적정성은 자동 재검증하지 않음',
           '부가가치세·기준연도·공종 간 실질적 중복은 사용자 검토 필요',
           '미산정 공종은 0원이 아니며 전체 총사업비는 미확정')
    return ProjectCost(construction,other,tuple(missing)+MISSING,str(cp),str(op),notes)

def export_project_cost(path,result):
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    from openpyxl.utils import get_column_letter
    wb=Workbook();wb.remove(wb.active)
    def sheet(name,header,rows):
        ws=wb.create_sheet(name);ws.append(header)
        for row in rows:ws.append(row)
        ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
        for cell in ws[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='17365D')
        for col in range(1,len(header)+1):ws.column_dimensions[get_column_letter(col)].width=35 if col<=2 else 56
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if isinstance(cell.value,(int,float)):cell.number_format='#,##0"원"'
    c=sum((v for _,v in result.construction),Decimal(0));o=sum((v for _,v in result.other),Decimal(0))
    sheet('총사업비산정분총괄',['구분','산정금액(원)','산정 상태'],[
        ('노반 공사비 산정분',int(c),'일부 산정'),('공사비 외 비용 산정분',int(o),'사용자 입력분'),
        ('산정분 합계',int(result.subtotal),'전체 총사업비 아님'),('전체 총사업비',None,'미확정: 미산정 공종 존재')])
    sheet('공사비구성',['공종','산정금액(원)','상태'],[
        (g,int(v),'산정') for g,v in result.construction]+[(g,None,'미산정') for g in result.missing])
    sheet('공사비외비용',['비용 분류','산정금액(원)','출처'],[(g,int(v),'T1/T2 JSON') for g,v in result.other])
    sheet('누락점검',['항목','상태','설명'],[(g,'미산정','0원으로 처리하지 않음') for g in result.missing])
    sheet('산정기준',['항목','내용'],[
        ('D5 원본',result.construction_file),('T1/T2 원본',result.other_file),
        ('가격 단위','원(KRW)'),('전체 총사업비','미확정')]+[(f'주의 {i}',n) for i,n in enumerate(result.notes,1)])
    wb.active=0;wb.save(path)
