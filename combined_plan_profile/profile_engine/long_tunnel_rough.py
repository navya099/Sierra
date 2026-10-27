"""U7: KDI 2019 III-77 long-tunnel rough cost. Pure calculation, no GUI dependencies.

Per independent TUNNEL segment >=10 km: mainline + inclined shafts + fire systems.
Does not change the frozen D5 rough estimator.
"""
from decimal import Decimal, InvalidOperation
from .cost_estimate import CostRow

THRESHOLD_M = Decimal('10000')
WON_PER_EOK = Decimal('100000000')
MAIN_EOK_KM = {1: Decimal('121'), 2: Decimal('169'), 3: Decimal('169')}
SHAFT_EOK_KM = Decimal('144')

def _decimal(value, label):
    try: x = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc: raise ValueError(f'{label}: 숫자를 입력하세요.') from exc
    if not x.is_finite(): raise ValueError(f'{label}: 유한한 숫자만 허용됩니다.')
    return x

def segment_key(segment):
    return (str(segment.start_sta), str(segment.end_sta))

def classify_tunnels(structures):
    """Classification is PER segment, not by aggregate tunnel length."""
    ordinary, long_tunnels = [], []
    for seg in structures:
        if seg.kind != 'TUNNEL': continue
        length = _decimal(seg.end_sta, '터널 종점') - _decimal(seg.start_sta, '터널 시점')
        if length <= 0: raise ValueError('터널 시종점이 잘못되었습니다.')
        (long_tunnels if length >= THRESHOLD_M else ordinary).append(seg)
    return ordinary, long_tunnels

def estimate_long_tunnels(segments, track_type, inputs):
    """inputs: {segment_key: {'shaft_length_km':str,'shaft_count':str,'fire_percent':str}}.

    Shaft length is PER shaft, count is integer, fire_percent is 1.0~1.5.
    Shaft count zero is allowed when explicitly specified; review project applicability.
    """
    if track_type not in MAIN_EOK_KM: raise ValueError('선로형식은 단선/복선/복선전철 중 하나여야 합니다.')
    _, longs = classify_tunnels(segments)
    rows=[]
    for idx,seg in enumerate(longs,1):
        key=segment_key(seg)
        if key not in inputs: raise ValueError(f'초장대터널 {idx}: 경사갱·방재설비 조건을 입력하세요.')
        cfg=inputs[key]
        km=(_decimal(seg.end_sta,'터널 종점')-_decimal(seg.start_sta,'터널 시점'))/Decimal(1000)
        mode=cfg.get('shaft_mode','simple')
        if mode=='individual':
            lengths=cfg.get('shaft_lengths_km',[])
            shaft_values=[_decimal(v,f'초장대터널 {idx} 경사갱 {j} 연장') for j,v in enumerate(lengths,1)]
            if any(v<=0 for v in shaft_values):raise ValueError(f'초장대터널 {idx}: 개별 경사갱 연장은 0보다 커야 합니다.')
            shaft_total=sum(shaft_values,Decimal(0))
            count=Decimal(len(shaft_values))
            shaft_label=f'{int(count)}개소 · 합계 {shaft_total}km'
            shaft_detail=' / 개별 경사갱 '+', '.join(f'{v}km' for v in shaft_values)+' (사용자 입력)'
        elif mode=='simple':
            shaft_km=_decimal(cfg.get('shaft_length_km',''),f'초장대터널 {idx} 경사갱 1개소 연장')
            count=_decimal(cfg.get('shaft_count',''),f'초장대터널 {idx} 경사갱 개소수')
            if shaft_km<0 or count<0 or count!=count.to_integral_value():raise ValueError(f'초장대터널 {idx}: 경사갱 연장은 0 이상, 개소수는 0 이상의 정수여야 합니다.')
            if count>0 and shaft_km<=0:raise ValueError(f'초장대터널 {idx}: 경사갱이 있으면 1개소 연장을 입력하세요.')
            shaft_total=shaft_km*count
            shaft_label=f'1개소 {shaft_km}km × {int(count)}개소'
            shaft_detail=f' / 경사갱 {shaft_km}km/개소 × {int(count)}개소 (사용자 입력)'
        else:raise ValueError(f'초장대터널 {idx}: 알 수 없는 경사갱 입력 방식')
        fire=_decimal(cfg.get('fire_percent',''),f'초장대터널 {idx} 방재설비 비율')
        if not Decimal('1.0')<=fire<=Decimal('1.5'):raise ValueError(f'초장대터널 {idx}: 방재설비 비율은 KDI 1.0~1.5% 범위여야 합니다.')
        label=seg.name.strip() if getattr(seg,'name','') else f'T{idx}'
        basis=f'KDI 2019 표 Ⅲ-77 / 보고서 p.110 / {label} STA {seg.start_sta:g}~{seg.end_sta:g}m / 본선 {km}km / 제비율 포함·VAT 제외'
        main_price=MAIN_EOK_KM[track_type]*WON_PER_EOK
        shaft_price=SHAFT_EOK_KM*WON_PER_EOK
        main=km*main_price
        # Retain all three independent cost components for auditability.
        rows.extend([
            CostRow('터널','TUNNEL_LONG_MAIN_S' if track_type==1 else 'TUNNEL_LONG_MAIN_D',f'{label} 초장대터널 본선',float(km),'km',float(main_price),float(main),basis+' / 본선'),
            CostRow('터널','TUNNEL_LONG_SHAFT',f'{label} 경사갱 ({shaft_label})',float(shaft_total),'km',float(shaft_price),float(shaft_total*shaft_price),basis+shaft_detail),
            CostRow('터널','TUNNEL_LONG_FIRE',f'{label} 방재설비 (본선비 {fire}%)',float(main),'원',float(fire/100),float(main*fire/100),basis+f' / 본선비 × {fire}% (사용자 입력)')
        ])
    return rows
