"""B.11: lightweight VIP station/index JSON and CSV vertical-curve inputs."""
import csv
import json
import math
from pathlib import Path
from .profile_engine.vertical_curve import VerticalAlignment


def _positive_length(value, context):
    try:
        length = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{context}: L은 숫자여야 합니다: {value!r}') from exc
    if not math.isfinite(length) or length <= 0:
        raise ValueError(f'{context}: L은 유한한 양수여야 합니다: {value!r}')
    return length


def _resolve_index(raw, points, context):
    if isinstance(raw, bool):
        raise ValueError(f'{context}: VIP 인덱스는 정수여야 합니다')
    try:
        idx = int(str(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{context}: VIP 인덱스는 정수여야 합니다: {raw!r}') from exc
    if str(raw).strip() != str(idx):
        raise ValueError(f'{context}: VIP 인덱스는 정수여야 합니다: {raw!r}')
    if not 0 < idx < len(points)-1:
        raise ValueError(f'{context}: 내부 VIP 인덱스 범위 오류 ({idx}; 허용 1~{len(points)-2})')
    return idx


def _resolve_station(raw, points, context, tolerance=0.001):
    try:
        sta = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{context}: VIP 측점은 숫자여야 합니다: {raw!r}') from exc
    if not math.isfinite(sta):
        raise ValueError(f'{context}: VIP 측점은 유한해야 합니다')
    matches = [i for i, (s, _) in enumerate(points) if abs(s-sta) <= tolerance]
    if not matches:
        nearest = min(range(len(points)), key=lambda i: abs(points[i][0]-sta))
        raise ValueError(f'{context}: 측점 {sta:g}m에 일치하는 VIP가 없습니다 (가장 가까운 VIP {nearest}: {points[nearest][0]:.6f}m)')
    if len(matches) != 1:
        raise ValueError(f'{context}: 측점 {sta:g}m의 VIP가 여러 개 일치합니다: {matches}')
    idx = matches[0]
    if not 0 < idx < len(points)-1:
        raise ValueError(f'{context}: 시작/끝 VIP에는 종곡선을 설정할 수 없습니다 (VIP {idx})')
    return idx


def load_simple_vertical_curves(path, vips, mode):
    """mode: 'station-json', 'index-json', or 'simple-csv'."""
    points = [(float(p.sta), float(p.elevation)) for p in vips]
    path = Path(path)
    lengths = {}
    if mode in ('station-json', 'index-json'):
        with path.open('r', encoding='utf-8-sig') as stream:
            data = json.load(stream, object_pairs_hook=_reject_duplicate_json_keys)
        if not isinstance(data, dict) or not data:
            raise ValueError('종곡선 JSON은 비어 있지 않은 {"VIP측점 또는 인덱스": L} 객체여야 합니다')
        rows = [(k, v, f'{path.name} 키 {k!r}') for k,v in data.items()]
    elif mode == 'simple-csv':
        with path.open('r', encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            headers = set(reader.fieldnames or [])
            if 'L' not in headers or ('VIP_STA' not in headers and 'VIP' not in headers):
                raise ValueError('간편 CSV 필수 열: VIP_STA,L 또는 VIP,L')
            if 'VIP_STA' in headers and 'VIP' in headers:
                raise ValueError('간편 CSV는 VIP_STA 또는 VIP 중 하나만 사용하세요')
            field = 'VIP_STA' if 'VIP_STA' in headers else 'VIP'
            mode = 'station-json' if field == 'VIP_STA' else 'index-json'
            rows = [(row[field], row['L'], f'{path.name} {n}행') for n,row in enumerate(reader,2)]
    else:
        raise ValueError(f'지원하지 않는 종곡선 입력 모드: {mode}')
    if not rows:
        raise ValueError('종곡선 입력에 적용할 항목이 없습니다')
    for raw, raw_length, context in rows:
        idx = (_resolve_station(raw,points,context) if mode=='station-json'
               else _resolve_index(raw,points,context))
        if idx in lengths:
            raise ValueError(f'{context}: VIP {idx} 중복 입력')
        lengths[idx] = _positive_length(raw_length,context)
    alignment = VerticalAlignment(points, lengths)  # overlaps/geometry validation
    return lengths, alignment


def _reject_duplicate_json_keys(pairs):
    result = {}
    for k,v in pairs:
        if k in result:
            raise ValueError(f'종곡선 JSON 키 중복: {k!r}')
        result[k] = v
    return result
