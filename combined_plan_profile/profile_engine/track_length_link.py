"""S2.1.1: derive track quantities from validated station and structure ranges.

Track lengths are centerline chainages, not surveyed 3-D rail lengths.
No assumptions are made about turnout counts, sidings, or real track counts.
"""
from decimal import Decimal
import math

def segment_lengths(vips, structures):
    if len(vips)<2: raise ValueError('종단 선형이 없습니다.')
    start,end=float(vips[0][0]),float(vips[-1][0])
    if not math.isfinite(start) or not math.isfinite(end) or end<=start:
        raise ValueError('노선 측점 범위가 유효하지 않습니다.')
    intervals=[]
    for s in structures:
        if s.kind not in ('BRIDGE','TUNNEL'):continue
        a,b=float(s.start_sta),float(s.end_sta)
        if not all(map(math.isfinite,(a,b))) or a<start-1e-6 or b>end+1e-6 or b<=a:
            raise ValueError(f'구조물 측점 범위 오류: {s.name or s.kind}')
        intervals.append((max(start,a),min(end,b),s.kind))
    intervals.sort()
    for left,right in zip(intervals,intervals[1:]):
        if right[0]<left[1]-1e-7:
            raise ValueError('구조물 측점이 중복됩니다. 구조물 목록을 정리하세요.')
    bridge=sum(b-a for a,b,k in intervals if k=='BRIDGE')
    tunnel=sum(b-a for a,b,k in intervals if k=='TUNNEL')
    earth=end-start-bridge-tunnel
    if earth<-1e-6:raise ValueError('구조물 연장이 전체 노선연장을 초과합니다.')
    return {'전체':Decimal(str(end-start)),'토공':Decimal(str(max(0,earth))),
            '교량':Decimal(str(bridge)),'터널':Decimal(str(tunnel))}

def quantity_for_price(row, lengths, track_count, scope):
    """Returns Decimal quantity in row unit; requires user-selected track count and scope."""
    if not isinstance(track_count,int) or track_count not in (1,2):
        raise ValueError('선로 수는 단선(1) 또는 복선(2)만 지원합니다.')
    if scope not in lengths:raise ValueError('산정 구간 선택 오류')
    code=str(row.get('code',''))
    unit=row.get('unit')
    if row.get('group')!='궤도':raise ValueError('궤도 단가만 자동 연동합니다.')
    length=lengths[scope]
    if code.startswith('TRACK_ROUGH_'):
        if scope!='전체':raise ValueError('개략 단가는 전체 노선연장만 적용합니다.')
        expected=1 if code.startswith('TRACK_ROUGH_S_') else 2
        if track_count!=expected:raise ValueError('선택한 KDI 개략 단가의 단선·복선 조건이 선로 수와 다릅니다.')
        if unit!='km':raise ValueError('개략 단가는 km 단위여야 합니다.')
        return length/Decimal(1000)
    if code in ('TRACK_DETAIL_BALLAST_INSTALL','TRACK_DETAIL_CONCRETE_INSTALL','TRACK_DETAIL_TRACK_REMOVE'):
        if unit!='m':raise ValueError('세부 궤도 단가는 m 단위여야 합니다.')
        return length*track_count
    raise ValueError('선로전환기 수량은 노선연장에서 자동 계산할 수 없습니다.')
