"""Sierra G1-2D-5-4: read-only multi-scale/multi-sheet DXF audit.
Python 3.11, ezdxf. Does not modify DXFs.
"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import re
import sys
import ezdxf

STRUCTURE_LAYERS = {
    'BRIDGE_SLAB_PLAN', 'BRIDGE_GIRDER_PLAN', 'BRIDGE_PIER_COLUMN_PLAN',
    'BRIDGE_PIER_COPING_PLAN', 'BRIDGE_FOUNDATION_PLAN', 'BRIDGE_ABUTMENT_PLAN',
    'TUNNEL_OUTER_PLAN', 'TUNNEL_INNER_PLAN', 'TUNNEL_PORTAL_PLAN',
}
LABEL_LAYER = 'STRUCTURE_LABEL_PLAN'
FILE_RE = re.compile(r'^종평면도\((\d+)\)\.dxf$', re.IGNORECASE)

def read_run(spec: str, tolerance: float):
    # name|directory|H|V|expected_paper_height|expected_color|sheet_length|end_sta
    fields = spec.split('|')
    if len(fields) != 8:
        raise ValueError('각 --run은 name|directory|H|V|height|color|sheet_length|end_sta 형식이어야 합니다')
    name, directory, h, v, height, color, length, end = fields
    h, v, height, length, end = map(float, (h, v, height, length, end))
    color = int(color)
    if min(h, v, height, length, end) <= 0 or not 1 <= color <= 255:
        raise ValueError('축척/높이/길이는 양수, 색상은 ACI 1~255여야 합니다')
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f'{name}: 폴더 없음: {root}')
    files = []
    for path in root.glob('*.dxf'):
        m = FILE_RE.fullmatch(path.name)
        if m:
            files.append((int(m.group(1)), path))
    files.sort()
    expected_count = int((end - tolerance) // length) + (1 if (end - tolerance) % length > 0 else 0)
    # Use ceil with a small tolerance for floating-point station boundaries.
    import math
    expected_count = math.ceil((end - tolerance) / length)
    indices = [i for i, _ in files]
    if indices != list(range(1, expected_count + 1)):
        raise AssertionError(f'{name}: 시트 인덱스 {indices}, 기대 1~{expected_count}')
    label_pairs = []
    total = Counter()
    print(f'\n[{name}] H{h:g}/V{v:g} | {len(files)} sheets | {root}')
    for index, path in files:
        doc = ezdxf.readfile(path)
        msp = doc.modelspace()
        counts = Counter()
        texts = []
        for ent in msp:
            layer = ent.dxf.get('layer', '0')
            if layer in STRUCTURE_LAYERS:
                counts[layer] += 1
            if layer != LABEL_LAYER or ent.dxftype() != 'TEXT':
                continue
            text = ent.dxf.text.strip()
            actual_height = float(ent.dxf.height)
            if abs(actual_height - height) > tolerance:
                raise AssertionError(f'{name} sheet {index}: TEXT {text!r} height {actual_height:g} != {height:g}')
            aci = int(ent.dxf.get('color', 256))
            if aci == 256:
                if layer not in doc.layers:
                    raise AssertionError(f'{name} sheet {index}: {layer} 레이어가 없음')
                aci = abs(int(doc.layers.get(layer).dxf.color))
            if aci != color:
                raise AssertionError(f'{name} sheet {index}: TEXT {text!r} ACI {aci} != {color}')
            texts.append(text)
        if len(texts) % 2:
            raise AssertionError(f'{name} sheet {index}: 주석 TEXT 홀수 {len(texts)}개; 제목/측점 쌍 확인 필요')
        for i in range(0, len(texts), 2):
            label_pairs.append((texts[i], texts[i+1]))
        total.update(counts)
        print(f'  sheet {index:2d}: modelspace={len(msp):5d} plan-labels={len(texts):2d} structure-entities={sum(counts.values()):5d}')
    duplicates = [pair for pair, count in Counter(label_pairs).items() if count > 1]
    if duplicates:
        raise AssertionError(f'{name}: 시트 간 중복 구조물 시작 주석: {duplicates[:5]}')
    print(f'  [PASS] 시트 {expected_count}개 연속 / 주석 {len(label_pairs)}쌍 / 높이 {height:g} / 색상 {color} / 중복 없음')
    print('  [INFO] 구조물 레이어 집계:', dict(sorted(total.items())))
    return {'name': name, 'labels': set(label_pairs), 'total': total, 'sheets': len(files)}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='append', required=True,
                   help='name|directory|H|V|paper_height|ACI_color|sheet_length|end_sta; 반복 가능')
    p.add_argument('--tolerance', type=float, default=1e-4)
    p.add_argument('--compare-labels', action='store_true', help='모든 실행의 구조물 시작 주석 집합 비교')
    args = p.parse_args()
    if args.tolerance <= 0:
        p.error('--tolerance must be positive')
    try:
        runs = [read_run(spec, args.tolerance) for spec in args.run]
        if args.compare_labels and len(runs) >= 2:
            baseline = runs[0]
            for run in runs[1:]:
                missing = baseline['labels'] - run['labels']
                extra = run['labels'] - baseline['labels']
                if missing or extra:
                    raise AssertionError(f"{run['name']} vs {baseline['name']}: missing={sorted(missing)[:10]}, extra={sorted(extra)[:10]}")
                print(f"[PASS] 주석 집합 일치: {baseline['name']} = {run['name']} ({len(run['labels'])}쌍)")
        print('\n[PASS] G1-2D-5-4 자동 검사 통과')
        print('[MANUAL] CAD 형상/클리핑/주석 위치와 실제 종단 주석은 별도 육안 확인 필요')
        return 0
    except (ValueError, AssertionError, FileNotFoundError, ezdxf.DXFError) as exc:
        print(f'\n[FAIL] {exc}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
