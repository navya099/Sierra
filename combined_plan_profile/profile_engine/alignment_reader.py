"""Extract horizontal alignment IP parameters and turn directions from a DXF.

Usage: python alignment_reader.py "본선평면선형.dxf" [-o output_dir]
Dependencies: pip install ezdxf
No chainage/BC/EC is inferred: the DXF alone does not certify station origins.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
import ezdxf

PATTERNS = {
    'ip_no': re.compile(r'^IP\s*NO\.?\s*[:=]?\s*(\d+)\s*$', re.I),
    'ia': re.compile(r'^IA\s*=\s*(.+)$', re.I),
    'radius_m': re.compile(r'^R\s*=\s*([-+\d.]+)', re.I),
    'tl_m': re.compile(r'^T\.?L\.?\s*=\s*([-+\d.]+)', re.I),
    'cl_m': re.compile(r'^C\.?L\.?\s*=\s*([-+\d.]+)', re.I),
    'coord_x': re.compile(r'^X\s*=\s*([-+\d.]+)', re.I),
    'coord_y': re.compile(r'^Y\s*=\s*([-+\d.]+)', re.I),
}

def parse_block(block):
    data = {}
    for ent in block:
        if ent.dxftype() not in ('TEXT', 'MTEXT', 'ATTDEF'):
            continue
        raw = ent.dxf.text if ent.dxftype() != 'MTEXT' else ent.plain_text()
        value = ' '.join(raw.strip().split())
        for field, pattern in PATTERNS.items():
            match = pattern.match(value)
            if match:
                data[field] = match.group(1).strip()
                break
    required = ('ip_no', 'ia', 'radius_m', 'tl_m', 'cl_m', 'coord_x', 'coord_y')
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f'{block.name}: missing fields: {missing}')
    data['ip_no'] = int(data['ip_no'])
    for field in ('radius_m', 'tl_m', 'cl_m', 'coord_x', 'coord_y'):
        data[field] = float(data[field])
    data['block_name'] = block.name
    # DXF geometry uses easting as X and northing as Y; survey labels X/Y are reversed.
    data['cad_x'] = data['coord_y']
    data['cad_y'] = data['coord_x']
    return data

def cross_turn(p0, p1, p2):
    ax, ay = p1[0]-p0[0], p1[1]-p0[1]
    bx, by = p2[0]-p1[0], p2[1]-p1[1]
    cross = ax*by-ay*bx
    if abs(cross) < 1e-8 * math.hypot(ax, ay) * math.hypot(bx, by):
        return 'UNKNOWN', 0.0
    return ('LEFT', -6.0) if cross > 0 else ('RIGHT', 6.0)

def extract(path):
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    ips = [parse_block(doc.blocks[insert.dxf.name]) for insert in msp.query('INSERT')
           if insert.dxf.name.upper().startswith('IP_BLOCK_')]
    ips.sort(key=lambda x: x['ip_no'])
    if not ips:
        raise ValueError('No IP_Block_* INSERTs found')
    if len({ip['ip_no'] for ip in ips}) != len(ips):
        raise ValueError('Duplicate IP numbers')
    ip_lines = [e for e in msp.query('LWPOLYLINE') if e.dxf.layer == 'IP라인']
    if len(ip_lines) != 1:
        raise ValueError(f'Expected one IP라인 LWPOLYLINE, found {len(ip_lines)}')
    vertices = [(float(x), float(y)) for x, y in ip_lines[0].get_points('xy')]
    if len(vertices) != len(ips)+2:
        raise ValueError(f'IP라인 vertices {len(vertices)} != IP count {len(ips)} + 2')
    # The IP polyline is expected in increasing IP order, with start/end anchors.
    for index, ip in enumerate(ips):
        px, py = vertices[index+1]
        error = math.hypot(px-ip['cad_x'], py-ip['cad_y'])
        if error > 0.05:
            raise ValueError(f"IP-{ip['ip_no']} coordinate mismatch {error:.3f}m: check IP라인 order")
        direction, offset = cross_turn(*vertices[index:index+3])
        ip['direction'] = direction
        ip['band_offset_mm'] = offset
        ip['ip_line_vertex_index'] = index+1
        ip['coordinate_match_error_m'] = round(error, 6)
    return ips

# Source generator (본선선형계산v9.py) writes station annotations as
# ordinary TEXT on 곡선제원문자, in increasing IP / station order.
STATION_PATTERN = re.compile(
    r"^\s*(SP|PC|CP|PS|BC|EC|EP)\s*=\s*(?:(\d+)\s*km\s*)?(\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)

def parse_station_text(text):
    match = STATION_PATTERN.fullmatch(text.strip())
    if not match:
        raise ValueError(f"Unrecognized station annotation: {text!r}")
    label, km, metres = match.groups()
    sta = (int(km) * 1000 if km is not None else 0) + float(metres)
    if km is not None and not (0 <= float(metres) < 1000):
        raise ValueError(f"Invalid kilometre station: {text!r}")
    return label.upper(), round(sta, 2)

def extract_with_stations(path, *, cl_tolerance_m=0.03):
    """Read IP blocks, IP polyline and curve stations from the same DXF.

    A complete group is SP/PC/CP/PS (cubic) or BC/EC (simple).
    Order is based on source writer's IP order, not TEXT insertion coordinates.
    Raises instead of silently associating ambiguous/incomplete groups.
    """
    ips = extract(path)
    doc = ezdxf.readfile(str(path))
    texts = [ent.dxf.text for ent in doc.modelspace().query('TEXT')
             if ent.dxf.layer in ('곡선제원문자', '선형제원문자')]
    if not texts:
        raise ValueError('No curve station TEXT on 곡선제원문자/선형제원문자')
    annotations = [parse_station_text(t) for t in texts]
    groups = []
    current = []
    expected = None
    endpoint = None
    for label, sta in annotations:
        if label == 'EP':
            if current or len(groups) != len(ips) or endpoint is not None:
                raise ValueError('EP is not a valid final endpoint in this sequence')
            endpoint = sta
            continue
        if endpoint is not None:
            raise ValueError('Curve annotation found after EP')
        if not current:
            if label == 'SP':
                expected = ('SP', 'PC', 'CP', 'PS')
            elif label == 'BC':
                expected = ('BC', 'EC')
            else:
                raise ValueError(f'Curve must start with SP or BC, got {label}')
        if len(current) >= len(expected) or label != expected[len(current)]:
            raise ValueError(f'Unexpected {label} in curve group {len(groups)+1}; expected {expected[len(current)]}')
        if current and sta <= current[-1][1]:
            raise ValueError(f'Non-increasing curve station at {label}={sta}')
        current.append((label, sta))
        if len(current) == len(expected):
            groups.append(dict(current))
            current = []
    if current or len(groups) != len(ips):
        raise ValueError(f'Incomplete/unequal curve groups: {len(groups)} groups for {len(ips)} IPs')
    last_end = float('-inf')
    for ip, stations in zip(ips, groups):
        start_label, end_label = ('SP', 'PS') if 'SP' in stations else ('BC', 'EC')
        start, end = stations[start_label], stations[end_label]
        if start <= last_end:
            raise ValueError(f"IP-{ip['ip_no']}: curve stations overlap or are unordered")
        length = end - start
        delta = round(length - ip['cl_m'], 4)
        if abs(delta) > cl_tolerance_m:
            raise ValueError(f"IP-{ip['ip_no']}: curve length {length:.2f} vs CL {ip['cl_m']:.2f} (delta {delta:+.2f}m)")
        ip['curve_type'] = 'cubic' if start_label == 'SP' else 'simplecurve'
        ip['stations'] = stations
        ip['curve_start_sta_m'] = start
        ip['curve_end_sta_m'] = end
        ip['curve_mid_sta_m'] = round((start + end) / 2, 3)
        ip['cl_check_delta_m'] = delta
        last_end = end
    if endpoint is not None and endpoint < last_end:
        raise ValueError('EP precedes final curve end')
    return {'source_dxf': str(path), 'ip_count': len(ips),
            'alignment_end_sta_m': endpoint, 'ips': ips}

def flatten_ip(ip):
    row = {k: v for k, v in ip.items() if k != 'stations'}
    for key in ('SP', 'PC', 'CP', 'PS', 'BC', 'EC'):
        row[f'{key}_sta_m'] = ip['stations'].get(key, '')
    return row

def main():
    parser = argparse.ArgumentParser(description='Extract IP parameters, directions and curve station limits from DXF')
    parser.add_argument('dxf', type=Path)
    parser.add_argument('-o', '--output', type=Path, default=None)
    args = parser.parse_args()
    result = extract_with_stations(args.dxf)
    outdir = args.output or args.dxf.parent
    outdir.mkdir(parents=True, exist_ok=True)
    csvpath, jsonpath = outdir/'alignment_ips.csv', outdir/'alignment_ips.json'
    rows = [flatten_ip(ip) for ip in result['ips']]
    with csvpath.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    jsonpath.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    for ip in result['ips']:
        print(f"IP-{ip['ip_no']}: {ip['curve_type']} {ip['direction']:<5} "
              f"{ip['curve_start_sta_m']:.2f} -> {ip['curve_end_sta_m']:.2f}, "
              f"CL delta={ip['cl_check_delta_m']:+.3f}m")
    print(f"EP: {result['alignment_end_sta_m']} | CSV: {csvpath} | JSON: {jsonpath}")

if __name__ == '__main__':
    main()
