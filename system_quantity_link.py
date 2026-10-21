"""S2.3 system/building quantity rules; source prices are per route-km or station/area."""
from decimal import Decimal
import re

def selected_price(basis, selected, catalog):
    m=re.search(r'KDI 단가 DB 선택:\s*([A-Za-z0-9_]+)',basis)
    if not m: raise ValueError('먼저 통합 KDI 단가 선택창에서 단가를 선택하세요.')
    code=m.group(1)
    if selected and selected.get('code')==code:return selected
    row=next((r for r in catalog if r['code']==code),None)
    if row is None:raise ValueError('KDI 단가 코드를 찾을 수 없습니다.')
    return row

def system_quantity(row,lengths,tracks,stations=None,area=None,scope='전체'):
    if tracks not in (1,2):raise ValueError('선로 수는 1 또는 2로 선택하세요.')
    group=row['group'];code=row['code'];unit=row['unit'];method=row.get('method','')
    if group not in ('전력','전차선','신호','통신','건축'):
        raise ValueError('시스템·건축 자동 수량은 해당 공종에만 적용됩니다.')
    # Each catalog km price already encodes single/double track; NEVER multiply by track count.
    if group=='건축':
        if unit!='m²':raise ValueError('건축은 면적(m²) 단가만 지원합니다.')
        if area is None or Decimal(str(area))<=0:raise ValueError('건축면적(m²)을 직접 입력하세요.')
        return Decimal(str(area)),'입력 건축면적(m²)'; 
    if group=='통신' and unit=='개소(역)':
        if stations is None or int(stations)!=stations or stations<0:
            raise ValueError('역 개소수를 0 이상의 정수로 입력하세요.')
        if stations==0:raise ValueError('역 개소수가 0입니다.')
        return Decimal(stations),'입력 역 개소수'
    if unit!='km':raise ValueError('이 항목은 연장으로 수량 산정할 수 없습니다.')
    if scope not in lengths:raise ValueError('유효하지 않은 산정 구간입니다.')
    if group=='전력':
        if method!='ROUGH':raise ValueError('전력은 검증된 개략(ROUGH) 단가만 지원합니다.')
        if not code.startswith('POWER_'):raise ValueError('전력 단가 코드를 확인하세요.')
        expected_scope='터널' if code.endswith('_TUN') else '토공'
        if scope!=expected_scope:raise ValueError(f'이 전력 단가는 {expected_scope} 구간에만 적용됩니다.')
    elif group=='전차선':
        if method!='DETAIL':raise ValueError('전차선은 검증된 세부(DETAIL) 단가만 지원합니다.')
        if not code.startswith('CAT_'):raise ValueError('전차선 단가 코드를 확인하세요.')
        expected_scope={'EARTH':'토공','BRIDGE':'교량','TUNNEL':'터널'}.get(code.split('_')[-1])
        if scope!=expected_scope:raise ValueError(f'이 전차선 단가는 {expected_scope} 구간에만 적용됩니다.')
    elif scope!='전체':
        raise ValueError('신호·통신 연장 단가는 전체 노선연장 기준으로 적용하세요.')
    if group in ('전력','전차선','신호','통신'):
        # The single/double-track condition is in the original per-route-km rate.
        if group=='전차선':
            expected=1 if '_S_' in code else 2
        elif group=='전력':
            expected=1 if code.startswith('POWER_S_') else 2
        elif group=='신호':
            expected=1 if code in ('SIG_S_GENERAL','SIG_GROUND_S','SIG_ATP_S') else 2
        else:
            expected=1 if code.endswith(('_S_NON_KM','_S_E_KM','_S_NON','_S_E')) else 2
        if tracks!=expected:raise ValueError('선택 단가의 단선/복선 조건과 입력 선로 수가 다릅니다.')
    value=lengths[scope]/Decimal(1000)
    if value<=0:raise ValueError('선택 구간의 연장이 0입니다.')
    return value,f'{scope} 노선연장 {lengths[scope]}m ÷ 1000 (선로수 {tracks}, 단가에 반영)'


def matching_section_prices(row, catalog):
    """Existing source prices only; never extrapolate bridge power unit price."""
    group=row['group'];code=row['code']
    if group=='전차선' and row.get('method')=='DETAIL':
        root=code.rsplit('_',1)[0]
        suffixes={'토공':'EARTH','교량':'BRIDGE','터널':'TUNNEL'}
        return {scope:next((r for r in catalog if r['code']==root+'_'+suffix),None)
                for scope,suffix in suffixes.items()}
    if group=='전력' and row.get('method')=='ROUGH':
        # Ground and tunnel are distinct rough prices, not a per-structure detail tariff.
        root=code[:-4] if code.endswith('_TUN') else code
        return {'토공':next((r for r in catalog if r['code']==root),None),
                '교량':None,
                '터널':next((r for r in catalog if r['code']==root+'_TUN'),None)}
    raise ValueError('구간 일괄 산정은 전력 개략 또는 전차선 세부 단가만 지원합니다.')

def batch_section_quantities(row,catalog,lengths,tracks,scopes):
    """Return individual, source-grounded line items; atomic validation before GUI insertion."""
    if not scopes:raise ValueError('산정할 구간을 선택하세요.')
    if len(set(scopes))!=len(scopes):raise ValueError('같은 구간을 중복 선택했습니다.')
    choices=matching_section_prices(row,catalog)
    result=[]
    for scope in scopes:
        if scope not in choices:raise ValueError(f'지원하지 않는 구간: {scope}')
        price=choices[scope]
        if price is None:raise ValueError(f'{scope} 구간의 {row["group"]} 원문 단가가 없어 자동 산정할 수 없습니다. 해당 구간은 미산정으로 유지하세요.')
        q,basis=system_quantity(price,lengths,tracks,scope=scope)
        result.append((scope,price,q,basis))
    return result
