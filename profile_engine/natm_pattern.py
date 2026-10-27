"""D4: explicit NATM pattern allocation; never infer geological patterns."""
from math import isfinite
from quantity_price import load_catalog

def pattern_codes(catalog=None):
    catalog=catalog or load_catalog()
    return {x['code']:x for x in catalog['items'] if x.get('method')=='DETAIL' and x['code'].startswith('TUNNEL_DETAIL_MAIN_P') and x.get('source_price_krw') is not None}

def allocate_natm(candidate, allocations, source_file, catalog=None, tolerance=0.001):
    """allocations: [(pattern price code, length in m), ...]. Returns estimate_detail entries."""
    if candidate.group!='터널' or 'NATM 미분류 전체연장' not in candidate.item:
        raise ValueError('NATM 미분류 터널 연장 후보만 분할할 수 있습니다.')
    prices=pattern_codes(catalog)
    selected=[];used=set();total=0.0
    for code,length in allocations:
        code=str(code).strip()
        try:q=float(length)
        except (TypeError,ValueError):raise ValueError(f'{code}: 패턴별 연장은 숫자여야 합니다.')
        if not isfinite(q) or q<0:raise ValueError(f'{code}: 패턴별 연장은 0 이상의 유한수여야 합니다.')
        if q==0:continue
        if code not in prices:raise ValueError(f'{code}: 검증된 NATM 본선 패턴 단가가 아닙니다.')
        if code in used:raise ValueError(f'{code}: 같은 터널에서 패턴 단가가 중복 지정되었습니다.')
        used.add(code);total+=q;selected.append((code,q))
    if not selected:raise ValueError('1개 이상의 패턴에 양의 연장을 입력하세요.')
    if abs(total-candidate.quantity)>tolerance:
        raise ValueError(f'{candidate.item}: 패턴 합계 {total:,.3f}m ≠ 터널 총연장 {candidate.quantity:,.3f}m (차이 {total-candidate.quantity:+,.3f}m)')
    source_id=str(source_file)+'::'+candidate.source
    return [{'code':code,'quantity':q,'source_id':source_id+'::'+code,
             'remark':f'{candidate.source} / NATM 패턴별 사용자 배분 {q:g}m / 원연장 {candidate.quantity:g}m / 사용자 확인'} for code,q in selected]
