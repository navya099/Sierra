"""Sierra S2: compare main-branch baseline and S1 renderer using the same input.

Usage: python test_s2_dxf_regression.py --baseline-zip path/to/Sierra-feature-profile-multiscale-v2.zip
Run from the S1 project directory. Does not modify project files.
"""
import argparse
import collections
import math
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import ezdxf


def signature(path):
    doc = ezdxf.readfile(str(path))
    rows = []
    for e in doc.modelspace():
        typ = e.dxftype()
        layer = e.dxf.layer
        if typ == 'LINE':
            data = (tuple(e.dxf.start), tuple(e.dxf.end))
        elif typ == 'LWPOLYLINE':
            data = tuple(tuple(p) for p in e.get_points('xyb'))
        elif typ == 'CIRCLE':
            data = (tuple(e.dxf.center), e.dxf.radius)
        elif typ == 'TEXT':
            data = (e.dxf.text, tuple(e.dxf.insert), tuple(e.dxf.get('align_point', (0, 0, 0))),
                    e.dxf.height, e.dxf.get('rotation', 0), e.dxf.get('halign', 0), e.dxf.get('valign', 0))
        elif typ == 'SOLID':
            data = tuple(tuple(e.dxf.get('vtx' + str(i), (0, 0, 0))) for i in range(4))
        else:
            raise AssertionError(f'Unsupported entity in regression: {typ} / {layer}')
        rows.append((typ, layer, data))
    return rows


def compare(a, b, tolerance=1e-7):
    if len(a) != len(b):
        raise AssertionError(f'Entity count differs: baseline={len(a)}, S1={len(b)}')
    for i, (left, right) in enumerate(zip(a, b)):
        def check(x, y, label):
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if not math.isclose(x, y, rel_tol=0, abs_tol=tolerance):
                    raise AssertionError(f'Entity {i} {label}: {x} != {y}')
            elif isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)) and len(x) == len(y):
                for j, (xx, yy) in enumerate(zip(x, y)):
                    check(xx, yy, f'{label}[{j}]')
            elif x != y:
                raise AssertionError(f'Entity {i} {label}: {x!r} != {y!r}')
        check(left, right, 'entity')


def render(project_dir, source, target, auto_datum, vertical_curve):
    code = '''from profile_drawing import create_profile_drawing, DrawingOptions
import sys
opts = DrawingOptions(horizontal_scale=1000, vertical_scale=400, auto_datum=(sys.argv[3]=='1'),
                      sheet_start_sta=200, sheet_end_sta=700)
create_profile_drawing(sys.argv[1],sys.argv[2],opts, vertical_curve_lengths=({1:200} if sys.argv[4]=='1' else None))'''
    proc = subprocess.run([sys.executable, '-c', code, str(source), str(target),
                           str(int(auto_datum)), str(int(vertical_curve))],
                          cwd=str(project_dir), capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f'Render failed in {project_dir}: {proc.stderr}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-zip', required=True)
    parser.add_argument('--s1-dir', default='.', help='Directory with S1 profile_drawing.py and profile_transform.py')
    args = parser.parse_args()
    s1 = Path(args.s1_dir).resolve()
    assert (s1 / 'profile_transform.py').exists(), 'S1 profile_transform.py missing'
    with tempfile.TemporaryDirectory(prefix='sierra_s2_') as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(args.baseline_zip) as z:
            # The supplied main baseline archive contains one top-level directory.
            z.extractall(tmp / 'baseline')
        roots = [p for p in (tmp / 'baseline').iterdir() if p.is_dir()]
        assert len(roots) == 1, 'Expected exactly one baseline root folder'
        baseline = roots[0]
        source = tmp / 'fixture.dxf'
        doc = ezdxf.new('R2010')
        doc.modelspace().add_lwpolyline([(0, 100), (450, 108), (900, 98)],
                                        dxfattribs={'layer': 'PLAN_PROFILE'})
        doc.modelspace().add_lwpolyline([(0, 103), (250, 107), (550, 109), (900, 102)],
                                        dxfattribs={'layer': 'GROUND_PROFILE'})
        doc.saveas(source)
        for auto_datum in (False, True):
            for vertical_curve in (False, True):
                tag = f'datum{int(auto_datum)}_vc{int(vertical_curve)}'
                old, new = tmp / f'old_{tag}.dxf', tmp / f'new_{tag}.dxf'
                render(baseline, source, old, auto_datum, vertical_curve)
                render(s1, source, new, auto_datum, vertical_curve)
                a, b = signature(old), signature(new)
                compare(a, b)
                counts = collections.Counter(layer for _, layer, _ in a)
                print(f'PASS {tag}: {len(a)} entities; {len(counts)} layers; coordinates/text identical')
    print('S2 regression: ALL 4 SCENARIOS PASSED')


if __name__ == '__main__':
    main()
