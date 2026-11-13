"""Compare modelspace entities outside elevation-pole layers in two DXFs.

Requires ezdxf. Exit 0: same; 1: mismatch; 2: invalid input.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json
import math
import sys

import ezdxf

EXCLUDED = {'ELEVATION_POLE', 'ELEVATION_POLE_TEXT', 'ELEVATION_POLE_NOTE'}
VOLATILE = {'handle', 'owner', 'reactors', 'extension_dict_handle'}


def normalize(v, digits):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        f = float(v)
        if not math.isfinite(f):
            return str(f)
        return round(f, digits)
    if isinstance(v, (str, bool)) or v is None:
        return v
    if isinstance(v, (tuple, list)):
        return [normalize(x, digits) for x in v]
    if hasattr(v, 'xyz'):
        return [normalize(x, digits) for x in v.xyz]
    if hasattr(v, '__iter__'):
        try:
            return [normalize(x, digits) for x in v]
        except (TypeError, ValueError):
            pass
    return str(v)


def signature(e, digits):
    attrs = {k: normalize(v, digits) for k, v in e.dxf.all_existing_dxf_attribs().items()
             if k not in VOLATILE}
    extra = None
    kind = e.dxftype()
    if kind == 'LWPOLYLINE':
        extra = [normalize(p, digits) for p in e.get_points('xyseb')]
    elif kind == 'POLYLINE':
        extra = {'vertices': [normalize(v.dxf.all_existing_dxf_attribs().get('location'), digits)
                              for v in e.vertices],
                 'bulges': [normalize(v.dxf.get('bulge', 0), digits) for v in e.vertices]}
    elif kind == 'SPLINE':
        extra = {'control_points': normalize(e.control_points, digits),
                 'fit_points': normalize(e.fit_points, digits),
                 'knots': normalize(e.knots, digits),
                 'weights': normalize(e.weights, digits)}
    elif kind in ('MTEXT', 'ATTRIB', 'ATTDEF'):
        extra = e.text if kind == 'MTEXT' else e.dxf.get('text', '')
    elif kind == 'INSERT':
        extra = {'attribs': sorted((a.dxf.get('tag', ''), a.dxf.get('text', ''),
                                    normalize(a.dxf.get('insert'), digits)) for a in e.attribs)}
    elif kind == 'HATCH':
        extra = str(e.paths)  # conservative: noncanonical representation may produce false positives
    return json.dumps([kind, attrs, extra], sort_keys=True, ensure_ascii=False)


def collect(path, digits):
    doc = ezdxf.readfile(str(path))
    groups = defaultdict(Counter)
    excluded = Counter()
    for e in doc.modelspace():
        layer = e.dxf.get('layer', '0')
        if layer in EXCLUDED:
            excluded[layer] += 1
        else:
            groups[(layer, e.dxftype())][signature(e, digits)] += 1
    return groups, excluded


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before', type=Path, required=True, help='DXF before elevation-pole changes')
    p.add_argument('--after', type=Path, required=True, help='DXF after elevation-pole changes')
    p.add_argument('--digits', type=int, default=6, help='Decimal places for numeric normalization (default 6)')
    p.add_argument('--max-examples', type=int, default=3)
    p.add_argument('--report', type=Path, help='Optional JSON mismatch report')
    args = p.parse_args()
    if args.digits < 0 or args.digits > 12 or args.max_examples < 0:
        p.error('digits must be 0..12 and max-examples >= 0')
    try:
        old, old_ex = collect(args.before, args.digits)
        new, new_ex = collect(args.after, args.digits)
    except (OSError, ezdxf.DXFError, ValueError) as exc:
        print('[ERROR]', exc)
        return 2
    old_total = sum(sum(c.values()) for c in old.values())
    new_total = sum(sum(c.values()) for c in new.values())
    print('[BEFORE]', args.before, 'non-pole=', old_total, 'excluded=', dict(old_ex))
    print('[AFTER] ', args.after, 'non-pole=', new_total, 'excluded=', dict(new_ex))
    differences = []
    for layer, kind in sorted(set(old) | set(new)):
        removed = old[(layer, kind)] - new[(layer, kind)]
        added = new[(layer, kind)] - old[(layer, kind)]
        if removed or added:
            n_removed, n_added = sum(removed.values()), sum(added.values())
            print(f'[DIFF] layer={layer} type={kind} removed={n_removed} added={n_added}')
            examples = {'removed': [{'count': count, 'signature': key} for key, count in removed.most_common(args.max_examples)],
                        'added': [{'count': count, 'signature': key} for key, count in added.most_common(args.max_examples)]}
            differences.append({'layer': layer, 'type': kind, 'removed': n_removed, 'added': n_added, 'examples': examples})
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({'before': str(args.before), 'after': str(args.after),
                                           'digits': args.digits, 'differences': differences},
                                          ensure_ascii=False, indent=2), encoding='utf-8')
        print('[REPORT]', args.report)
    if differences:
        print(f'[RESULT] FAIL ({len(differences)} layer/type groups differ)')
        return 1
    print('[RESULT] PASS (all non-pole modelspace entities match)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
