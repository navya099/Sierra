"""T2 optional percent calculator. T1 storage format remains unchanged."""
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from .nonconstruction_cost import parse_amount

def calculate(base,percent):
    base=parse_amount(base)
    try: rate=Decimal(str(percent).strip().replace(',',''))
    except (InvalidOperation,ValueError): raise ValueError('적용 요율은 숫자여야 합니다.') from None
    if not rate.is_finite() or rate<0 or rate>100:
        raise ValueError('적용 요율은 0~100% 범위여야 합니다.')
    value=(base*rate/Decimal('100')).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
    return value,rate

def calculation_basis(base,rate,source,rule):
    if not source.strip(): raise ValueError('기준금액의 출처를 입력하세요.')
    if not rule.strip(): raise ValueError('요율 적용 근거를 입력하세요.')
    return (f'[T2 요율계산] 기준금액 {int(base):,}원 × {rate}% / 100; '
            f'기준금액 출처: {source.strip()}; 요율 근거: {rule.strip()}; '
            '원 단위 반올림(ROUND_HALF_UP)')
