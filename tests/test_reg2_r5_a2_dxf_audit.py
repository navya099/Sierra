"""REG2-R5-A-2-4 DXF entity audit. Run with Python 3.11 and ezdxf.

Usage:
 python test_reg2_r5_a2_dxf_audit.py --dxf path.dxf --preset profile_presets/cad/h5000_v1000.json
 python test_reg2_r5_a2_dxf_audit.py --dxf new.dxf --preset ... --legacy old.dxf
 Optional single-pole datum: --datum-left 180 --graph-datum-y 1000
 Multi-pole datum (left to right): --pole-datums 180 230 280 330 --graph-datum-y 1000
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import sys
import ezdxf

POLE_LAYERS = {'ELEVATION_POLE', 'ELEVATION_POLE_TEXT', 'ELEVATION_POLE_NOTE'}
EPS = 1e-5

def near(a, b, tol=EPS):
    return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)

def read_entities(path):
    return list(ezdxf.readfile(str(path)).modelspace())

def xy(v):
    return (float(v[0]), float(v[1]))

def solid_box(ent):
    pts = [xy(ent.dxf.get(name)) for name in ('vtx0', 'vtx1', 'vtx2', 'vtx3')]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

def text_position(ent):
    # _text() uses set_placement(MIDDLE_LEFT), which writes the alignment point.
    align = ent.dxf.get('align_point', None)
    return xy(align if align is not None else ent.dxf.insert)

def entity_signature(e):
    """Compare non-pole entities without relying on volatile DXF handles."""
    attrs = e.dxf.all_existing_dxf_attribs()
    attrs = {k: str(v) for k, v in attrs.items() if k not in {'handle', 'owner'}}
    geom = None
    if e.dxftype() == 'LWPOLYLINE':
        geom = [tuple(round(float(v), 6) for v in p) for p in e.get_points('xyseb')]
    elif e.dxftype() == 'POLYLINE':
        geom = [tuple(round(float(c), 6) for c in v.dxf.location) for v in e.vertices]
    elif e.dxftype() == 'SPLINE':
        geom = [tuple(round(float(c), 6) for c in p) for p in e.control_points]
    return json.dumps([e.dxftype(), sorted(attrs.items()), geom], ensure_ascii=False, sort_keys=True)

def audit(dxf, preset_path, legacy=None, datum_left=None, graph_datum_y=None, pole_datums=None):
    preset = json.loads(Path(preset_path).read_text(encoding='utf-8-sig'))
    style = preset['layout']['annotations']['elevation_pole']
    enabled = style['enabled']
    width = float(style['solid']['width'])
    stripe = float(style['solid']['stripe_height'])
    color = int(style['solid']['color'])
    interval = float(style['labels']['interval_m'])
    height = float(style['labels']['text_height'])
    leader = float(style['labels']['leader_length'])
    vertical_scale = float(preset['vertical_scale'])
    ents = read_entities(dxf)
    pole = [e for e in ents if e.dxf.layer in POLE_LAYERS]
    solids = [e for e in pole if e.dxftype() == 'SOLID' and e.dxf.layer == 'ELEVATION_POLE']
    texts = [e for e in pole if e.dxftype() == 'TEXT' and e.dxf.layer == 'ELEVATION_POLE_TEXT']
    lines = [e for e in pole if e.dxftype() == 'LINE' and e.dxf.layer == 'ELEVATION_POLE_TEXT']
    failures = []
    warnings = []
    def check(cond, message):
        if not cond:
            failures.append(message)
    print(f'[AUDIT] {dxf} | H={preset["horizontal_scale"]}, V={vertical_scale:g}')
    print(f'[ENTITIES] pole={len(pole)} SOLID={len(solids)} TEXT={len(texts)} leader LINE={len(lines)}')
    if not enabled:
        check(not pole, 'enabled=false, but pole entities exist')
    else:
        check(bool(solids), 'No ELEVATION_POLE SOLID found')
        for i, e in enumerate(solids):
            x0, y0, x1, y1 = solid_box(e)
            check(near(x1-x0, width/2), f'SOLID[{i}] half-width {x1-x0:g} != {width/2:g}')
            check(0 < y1-y0 <= stripe+EPS, f'SOLID[{i}] stripe height {y1-y0:g} exceeds {stripe:g}')
            check(e.dxf.get('color', 256) == color, f'SOLID[{i}] color {e.dxf.get("color", 256)} != {color}')
        # Group by left pole coordinate (solid alternates left and right halves).
        # Each SOLID's center is either pole_left+width/4 or pole_left+3*width/4.
        # Check vertical step independently within each SOLID x-column.
        columns = defaultdict(list)
        for e in solids:
            x0,y0,x1,y1=solid_box(e)
            columns[round(x0, 4)].append((y0,y1))
        for x, items in columns.items():
            items.sort(key=lambda t:t[1], reverse=True)
            for upper, lower in zip(items, items[1:]):
                gap=upper[0]-lower[1]
                check(near(gap, stripe, 1e-3) or near(gap, stripe*1, 1e-3),
                      f'SOLID column x={x:g} vertical gap {gap:g} != {stripe:g}')
        numeric=[]
        for e in texts:
            s=e.dxf.text.strip()
            try:
                value=float(s)
            except ValueError:
                continue  # e.g. multi-datum reference annotation
            numeric.append((value, text_position(e), e))
            check(near(e.dxf.height, height), f'EL.{value:g} TEXT height {e.dxf.height:g} != {height:g}')
        check(bool(numeric), 'No numeric elevation TEXT found (check elevation_pole_labels option)')
        print('[EL LABELS]', [(v, round(pos[1], 3)) for v,pos,_ in numeric])
        for value, pos, e in numeric:
            check(near(value / interval, round(value / interval), 1e-6),
                  f'EL.{value:g} not multiple of {interval:g}m')
            matching = [ln for ln in lines if near(ln.dxf.start.y, ln.dxf.end.y)
                        and near(ln.dxf.start.x, pos[0]) and near(ln.dxf.start.y, pos[1]-3.0)]
            check(bool(matching), f'EL.{value:g} leader line missing at expected text offset 3.0')
            if matching:
                ln=matching[0]
                check(near(abs(ln.dxf.end.x-ln.dxf.start.x), leader),
                      f'EL.{value:g} leader length mismatch')
        # A combined sheet can contain multiple poles with overlapping Y ranges.
        # Group labels by their leader-start X, not by global Y order.
        label_columns = defaultdict(list)
        unmatched = 0
        for value, pos, ent in numeric:
            matching = [ln for ln in lines
                        if near(ln.dxf.start.y, ln.dxf.end.y)
                        and near(ln.dxf.start.x, pos[0])
                        and near(ln.dxf.start.y, pos[1] - 3.0)]
            if not matching:
                unmatched += 1
                continue
            label_columns[round(float(matching[0].dxf.start.x), 4)].append((value, pos[1]))
        print(f'[LABEL GROUPS] poles={len(label_columns)} unmatched={unmatched}')
        # Absolute datum audit must use the datum belonging to each X-group.
        # Never apply one datum to all poles on a multi-pole sheet.
        sorted_columns = sorted(label_columns.items())
        if pole_datums is not None or datum_left is not None:
            if graph_datum_y is None:
                check(False, 'Datum check requested without --graph-datum-y')
            else:
                datums = pole_datums if pole_datums is not None else [datum_left]
                if len(datums) != len(sorted_columns):
                    check(False, f'Datum count {len(datums)} != pole group count {len(sorted_columns)}; use --pole-datums for multi-pole DXF')
                else:
                    for (x, entries), datum in zip(sorted_columns, datums):
                        for value, text_y in entries:
                            leader_y = text_y - 3.0
                            expected_y = graph_datum_y + (value - datum) * 1000.0 / vertical_scale
                            check(near(leader_y, expected_y, 1e-3),
                                  f'Pole X={x:g}, datum={datum:g}, EL.{value:g}: label Y={leader_y:g} expected {expected_y:g}')
                    print(f'[DATUM] groups={len(sorted_columns)} datums={datums} graph_datum_y={graph_datum_y:g}')

        expected_dy = interval * 1000.0 / vertical_scale
        for x, entries in sorted(label_columns.items()):
            entries.sort(key=lambda item: item[1])
            for (v0, y0), (v1, y1) in zip(entries, entries[1:]):
                check(near(v1 - v0, interval, 1e-3),
                      f'Pole leader X={x:g}: EL increment {v1-v0:g} != {interval:g}')
                check(near(y1 - y0, expected_dy, 1e-3),
                      f'Pole leader X={x:g}: Y increment {y1-y0:g} != {expected_dy:g}')
        if datum_left is None and pole_datums is None:
            warnings.append('Datum-based absolute EL check skipped; supply --pole-datums and --graph-datum-y')
    if legacy:
        old=read_entities(legacy)
        new_counter=Counter(entity_signature(e) for e in ents if e.dxf.layer not in POLE_LAYERS)
        old_counter=Counter(entity_signature(e) for e in old if e.dxf.layer not in POLE_LAYERS)
        check(new_counter==old_counter, f'Non-pole entity mismatch: added={sum((new_counter-old_counter).values())}, removed={sum((old_counter-new_counter).values())}')
        print(f'[REGRESSION] non-pole entities: old={sum(old_counter.values())} new={sum(new_counter.values())}')
    else:
        warnings.append('Non-pole regression comparison skipped; supply --legacy with same-input DXF')
    for m in warnings: print('[SKIP]',m)
    for m in failures: print('[FAIL]',m)
    if failures:
        print(f'[RESULT] FAIL ({len(failures)} issues)')
        return 1
    print('[RESULT] PASS (performed checks only; see SKIP items)')
    return 0

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dxf', type=Path, required=True)
    p.add_argument('--preset', type=Path, required=True)
    p.add_argument('--legacy', type=Path)
    p.add_argument('--datum-left', type=float)
    p.add_argument('--pole-datums', type=float, nargs='+', help='Pole datums in ascending X order')
    p.add_argument('--graph-datum-y', type=float)
    args=p.parse_args()
    return audit(
        dxf=args.dxf,
        preset_path=args.preset,
        legacy=args.legacy,
        datum_left=args.datum_left,
        graph_datum_y=args.graph_datum_y,
        pole_datums=args.pole_datums,
    )

if __name__=='__main__':
    sys.exit(main())
