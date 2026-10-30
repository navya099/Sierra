"""Load vertical_curve_result.csv exported by the original GUI."""
import csv
import math
from pathlib import Path
from .profile_engine.vertical_curve import VerticalAlignment


def load_vertical_curve_csv(path, vips):
    points = [(float(p.sta), float(p.elevation)) for p in vips]
    lengths = {}
    with Path(path).open('r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'VIP', 'VIP_STA', 'VIP_EL', 'L'}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError('종곡선 CSV 필수 열: VIP, VIP_STA, VIP_EL, L')
        for rowno, row in enumerate(reader, 2):
            try:
                idx = int(row['VIP'])
                sta = float(row['VIP_STA'])
                el = float(row['VIP_EL'])
                length = float(row['L'])
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f'종곡선 CSV {rowno}행: VIP/측점/표고/L 형식 오류') from exc
            if not 0 < idx < len(points)-1:
                raise ValueError(f'종곡선 CSV {rowno}행: 내부 VIP 인덱스 범위 오류 ({idx})')
            if not all(map(math.isfinite, (sta, el, length))) or length <= 0:
                raise ValueError(f'종곡선 CSV {rowno}행: 유한한 양수 L 및 측점/표고 필요')
            actual_sta, actual_el = points[idx]
            if abs(sta-actual_sta)>0.001 or abs(el-actual_el)>0.001:
                raise ValueError(f'종곡선 CSV {rowno}행: VIP {idx} 측점/표고가 입력 DXF와 다릅니다 (CSV STA={sta}, EL={el}; DXF STA={actual_sta}, EL={actual_el})')
            if idx in lengths:
                raise ValueError(f'종곡선 CSV {rowno}행: VIP {idx} 중복')
            lengths[idx] = length
    if not lengths:
        raise ValueError('종곡선 CSV에 적용할 종곡선이 없습니다.')
    alignment = VerticalAlignment(points, lengths)
    return lengths, alignment
