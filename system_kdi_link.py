"""S2: verified-price selection adapter. No missing prices are synthesized."""
from decimal import Decimal
from pathlib import Path
import json
from system_building_cost import GROUPS, number

REQUIRED=('code','group','name','unit','source_price_krw','source_year','source_table','source_page')

def load_eligible_catalog(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data,dict) or not isinstance(data.get('items'),list):
        raise ValueError('단가 DB는 items 배열이 포함된 JSON이어야 합니다.')
    found=[];codes=set()
    for n,row in enumerate(data['items'],1):
        if not isinstance(row,dict):raise ValueError(f'{n}번 단가 항목 형식 오류')
        if row.get('group') not in GROUPS:continue
        if any(row.get(k) is None or str(row.get(k)).strip()=='' for k in REQUIRED):
            raise ValueError(f'{n}번 단가: 출처 또는 필수 항목 누락')
        code=str(row['code']).strip()
        if code in codes:raise ValueError(f'단가 코드 중복: {code}')
        codes.add(code)
        price=number(row['source_price_krw'],'원 단가',positive=True)
        if price!=price.to_integral_value():raise ValueError(f'{code}: 원 단위 정수 단가만 허용')
        if int(row['source_year'])<1900 or int(row['source_year'])>2100:raise ValueError(f'{code}: 기준연도 오류')
        found.append({**row,'source_price_krw':int(price)})
    return found

def provenance(row,db_name):
    return (f"KDI 단가 DB 선택: {row['code']} | {row['source_year']}년 기준 | "
            f"표 {row['source_table']} / p.{row['source_page']} | "
            f"단가 출처 파일: {db_name} | 물가보정 없음 | "
            f"수량 근거 별도 확인 필요")
