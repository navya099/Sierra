"""U10 station interval classification. Read-only analysis of existing BRIDGE/TUNNEL ranges."""
from decimal import Decimal, InvalidOperation

def number(value, label):
    try: n=Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc: raise ValueError(f'{label}: 숫자를 입력하세요.') from exc
    if not n.is_finite(): raise ValueError(f'{label}: 유한한 숫자를 입력하세요.')
    return n

def classify_station(name, start, end, structures, route_start, route_end):
    a=number(start,'정거장 시작 STA');b=number(end,'정거장 끝 STA')
    lo=number(route_start,'노선 시작 STA');hi=number(route_end,'노선 끝 STA')
    if not lo<=a<b<=hi: raise ValueError(f'{name}: 정거장 구간이 노선 범위를 벗어나거나 길이가 0 이하입니다.')
    intervals=[]
    for s in structures:
        if s.kind not in ('BRIDGE','TUNNEL'):continue
        x=number(s.start_sta,'구조물 시작 STA');y=number(s.end_sta,'구조물 끝 STA')
        if not lo<=x<y<=hi: raise ValueError(f'구조물 범위 오류: {s.name}')
        intervals.append((x,y,s.kind))
    intervals.sort()
    for left,right in zip(intervals,intervals[1:]):
        if right[0]<left[1]: raise ValueError('교량·터널 구간이 중복됩니다. 기존 구조물 목록을 확인하세요.')
    boundaries={a,b}
    for x,y,_ in intervals:
        if a<x<b:boundaries.add(x)
        if a<y<b:boundaries.add(y)
    pts=sorted(boundaries);pieces=[]
    for x,y in zip(pts,pts[1:]):
        kind=next((k for u,v,k in intervals if u<=x and y<=v),'EARTH')
        if pieces and pieces[-1]['kind']==kind and pieces[-1]['end']==x:pieces[-1]['end']=y
        else:pieces.append({'kind':kind,'start':x,'end':y})
    names={'EARTH':'토공','BRIDGE':'교량','TUNNEL':'터널'}
    lengths={k:sum((p['end']-p['start'] for p in pieces if p['kind']==k),Decimal(0)) for k in names}
    present=[k for k,v in lengths.items() if v>0]
    classification=names[present[0]]+' 단일' if len(present)==1 else '복합 (사용자 검토)'
    return {'name':name,'start':a,'end':b,'length':b-a,'pieces':pieces,'lengths':lengths,
            'sequence':'–'.join(names[p['kind']] for p in pieces),'classification':classification}

def add_station_segment_sheet(wb, results):
    ws=wb.create_sheet('정거장구간판별')
    ws.append(['정거장명','시작 STA(m)','끝 STA(m)','연장(m)','구조물 순서','판정','토공(m)','교량(m)','터널(m)','토공(%)','교량(%)','터널(%)','검토'])
    for r in results:
        length=r['length'];v=r['lengths']
        ws.append([r['name'],float(r['start']),float(r['end']),float(length),r['sequence'],r['classification'],
                   *[float(v[k]) for k in ('EARTH','BRIDGE','TUNNEL')],
                   *[float(v[k]/length*100) for k in ('EARTH','BRIDGE','TUNNEL')],
                   '공사비 자동 차감·단가 확정 미적용'])
    detail=wb.create_sheet('정거장구간상세')
    detail.append(['정거장명','순서','구조형식','시작 STA(m)','끝 STA(m)','중첩 연장(m)'])
    for r in results:
        for i,p in enumerate(r['pieces'],1):detail.append([r['name'],i,{'EARTH':'토공','BRIDGE':'교량','TUNNEL':'터널'}[p['kind']],float(p['start']),float(p['end']),float(p['end']-p['start'])])
    for sheet in (ws,detail):
        sheet.freeze_panes='A2'
        for col in sheet.columns:
            letter=col[0].column_letter
            sheet.column_dimensions[letter].width=min(38,max(17,max(len(str(c.value or '')) for c in col)+2))
    return ws
