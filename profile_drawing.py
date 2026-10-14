"""Generate a separate 1:1 railway longitudinal-profile drawing.

Source DXF is strictly read-only. No sheet scaling or sheet splitting here.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import math
import os

import ezdxf
from ezdxf.enums import TextEntityAlignment

from dxf_reader import extract_profile
from profile_calculator import PiecewiseLinear, read_ground_points, calculate_stations
from profile_layout import ProfileLayout


@dataclass(frozen=True)
class DrawingOptions:
    station_interval: float = 20.0
    major_interval: float = 200.0
    band_interval: float = 20.0
    graph_bottom: float | None = None
    bottom_margin: float = 12.0
    band_row_height: float = 6.0
    label_column_width: float = 22.0
    text_height: float = 2.0
    include_alignment_placeholder: bool = True
    annotation_row_height: float = 6.0
    grade_decimals: int = 1
    distance_decimals: int = 2
    vip_circle_radius: float = 2.2
    vip_elevation_decimals: int = 2
    vertical_scale: float = 400.0  # 1:V, reference horizontal scale 1:1000
    horizontal_scale: float = 1000.0
    origin_x: float = 0.0
    origin_y: float = 0.0


def _multiples(start: float, end: float, step: float) -> list[float]:
    if not math.isfinite(step) or step <= 0:
        raise ValueError('간격은 0보다 큰 유한한 수여야 합니다.')
    i0 = math.ceil((start - 1e-8) / step)
    i1 = math.floor((end + 1e-8) / step)
    return [i * step for i in range(i0, i1 + 1)]


def _layer(doc, name, color, lineweight=25):
    doc.layers.new(name, dxfattribs={'color': color, 'lineweight': lineweight})


def _text(msp, text, x, y, height, layer, rotation=0, align=TextEntityAlignment.MIDDLE_CENTER):
    entity = msp.add_text(str(text), dxfattribs={
        'layer': layer, 'height': height, 'rotation': rotation, 'style': 'KOREAN'
    })
    entity.set_placement((x, y), align=align)
    return entity


def _line(msp, x1, y1, x2, y2, layer):
    return msp.add_line((x1, y1), (x2, y2), dxfattribs={'layer': layer})


def _fmt_grade(value, decimals=1):
    # Conventional longitudinal-profile grade: 3.0 (unit: permille)
    return f'{value:.{decimals}f}' if value is not None else '—'


def _fmt_distance(metres: float) -> str:
    negative = metres < 0
    metres = abs(metres)
    # Round before dividing to avoid 1km1000.00 near a kilometre boundary.
    hundredths = int(round(metres * 100))
    km, remainder = divmod(hundredths, 100000)
    result = f'{km}km{remainder / 100:06.2f}'
    return '-' + result if negative else result


def create_profile_drawing(source_dxf: str | Path, output_dxf: str | Path,
                           options: DrawingOptions | None = None) -> dict:
    """Build final_result.dxf without ever modifying the source drawing."""
    options = options or DrawingOptions()
    source = Path(source_dxf).resolve()
    output = Path(output_dxf).resolve()
    if source == output:
        raise ValueError('입력 DXF와 출력 DXF는 서로 달라야 합니다.')
    if not all(math.isfinite(v) and v > 0 for v in (options.vertical_scale, options.horizontal_scale)):
        raise ValueError('출력 축척은 양수여야 합니다.')
    if options.band_row_height <= 0 or options.text_height <= 0 or options.bottom_margin <= 0 or options.annotation_row_height <= 0 or options.vip_circle_radius <= 0:
        raise ValueError('밴드 높이, 문자 높이, 하단 여백은 양수여야 합니다.')
    if options.station_interval <= 0 or options.major_interval <= 0 or options.band_interval <= 0:
        raise ValueError('그리드/밴드 간격은 양수여야 합니다.')

    ground_points = read_ground_points(source)
    vip = extract_profile(source)
    plan_points = [(p.sta, p.elevation) for p in vip]
    raw_ground = PiecewiseLinear(ground_points)
    raw_plan = PiecewiseLinear(plan_points)
    ground = raw_ground
    plan = raw_plan
    start = max(ground.xs[0], plan.xs[0])
    end = min(ground.xs[-1], plan.xs[-1])
    if end <= start:
        raise ValueError('지반선과 계획 종단선의 공통 측점 범위가 없습니다.')

    # Graph baseline must be below both lines over the displayed interval.
    relevant = [start, end]
    relevant += [x for x, _ in ground_points if start < x < end]
    relevant += [x for x, _ in plan_points if start < x < end]
    lowest = min(min(ground.at(x)[0], plan.at(x)[0]) for x in relevant)
    graph_bottom = (lowest - options.bottom_margin if options.graph_bottom is None
                    else options.graph_bottom)
    if graph_bottom >= lowest:
        raise ValueError(f'종단면도 하단 표고({graph_bottom:.3f})는 최저 표고({lowest:.3f})보다 낮아야 합니다.')

    # Local drawing coordinates: band lower-left is the temporary origin.
    # All elevations and stations remain in source units until transformed.
    layout = ProfileLayout(origin_x=options.origin_x, origin_y=options.origin_y)
    graph_base_y = layout.origin_y + layout.band_top + 60.0
    def display_el(el):
        return layout.elevation_y(el, graph_bottom, layout.band_top + 60.0,
                                  options.vertical_scale)
    def display_sta(sta):
        return layout.station_x(sta, start, options.horizontal_scale)
    graph_bottom_y = graph_base_y
    data_left = display_sta(start)
    data_right = display_sta(end)
    label_left = layout.origin_x
    grade_rule_y = layout.grade_rule_y
    distance_rule_y = layout.distance_rule_y
    top = layout.origin_y + layout.band_top
    bottom = layout.origin_y
    factor = options.horizontal_scale / options.vertical_scale
    doc = ezdxf.new('R2010')
    doc.header['$INSUNITS'] = 4  # millimetres: output paper-space geometry
    doc.styles.new('KOREAN', dxfattribs={'font': 'malgun.ttf'})
    _layer(doc, 'GROUND_PROFILE', 8, 0)
    _layer(doc, 'PLAN_PROFILE', 1, 100)
    _layer(doc, 'GRID_MINOR', 8, 0)
    _layer(doc, 'GRID_MAJOR', 6, 18)
    _layer(doc, 'VIP_ANNOTATION', 7, 18)
    _layer(doc, 'GRADE_DISTANCE_RULE', 7, 18)
    _layer(doc, 'VIP_MARKER', 7, 18)
    _layer(doc, 'PROFILE_BAND', 7, 18)
    _layer(doc, 'BAND_TEXT', 7, 0)
    msp = doc.modelspace()

    def clipped(poly, fn):
        return [(start, fn.at(start)[0])] + [(x, y) for x, y in poly if start < x < end] + [(end, fn.at(end)[0])]

    for poly, fn, layer in ((ground_points, raw_ground, 'GROUND_PROFILE'),
                            (plan_points, raw_plan, 'PLAN_PROFILE')):
        msp.add_lwpolyline([(display_sta(x), display_el(y)) for x, y in clipped(poly, fn)],
                           dxfattribs={'layer': layer})

    minor = _multiples(start, end, options.station_interval)
    major = _multiples(start, end, options.major_interval)
    major_set = set(major)
    for sta in minor:
        if sta not in major_set:
            _line(msp, display_sta(sta), display_el(raw_ground.at(sta)[0]),
                  display_sta(sta), graph_bottom_y, 'GRID_MINOR')
    for sta in major:
        _line(msp, display_sta(sta), display_el(raw_ground.at(sta)[0]),
              display_sta(sta), graph_bottom_y, 'GRID_MAJOR')

    # Reference layout: band rows from bottom up, 20/20/20/15/15.
    # With the optional alignment row off, retain its reserved space.
    rows = [('평면선형', 0, 20), ('지반고', 20, 40), ('계획고', 40, 60),
            ('성토고', 60, 75), ('절토고', 75, 90)]
    if not options.include_alignment_placeholder:
        rows = rows[1:]
    for y in (0, 20, 40, 60, 75, 90):
        _line(msp, label_left, layout.origin_y+y, data_right,
              layout.origin_y+y, 'PROFILE_BAND')
    for x in (label_left, data_left, data_right):
        _line(msp, x, bottom, x, top, 'PROFILE_BAND')
    for name, low, high in rows:
        _text(msp, name, (label_left + data_left)/2,
              layout.origin_y+(low+high)/2,
              layout.label_text_height, 'BAND_TEXT')

    band_stations = sorted(set(_multiples(start, end, options.band_interval) + [start, end]))
    for sta in band_stations:
        g = raw_ground.at(sta)[0]
        p = raw_plan.at(sta)[0]
        vals = ((max(g-p, 0), 75, 90), (max(p-g, 0), 60, 75),
                (g, 20, 40), (p, 40, 60))
        for idx, (value, low, high) in enumerate(vals):
            if idx < 2 and value <= 1e-7:
                continue
            _text(msp, f'{value:.2f}', display_sta(sta),
                  layout.origin_y+(low+high)/2,
                  layout.data_text_height, 'BAND_TEXT', rotation=90)
    # No internal vertical lines in the band: user-approved cleanup.

    circle_stations = sorted(p.sta for p in vip
                             if p.kind.startswith('VIP') and start < p.sta < end)
    r = options.vip_circle_radius
    cursor = data_left
    for sta in circle_stations:
        x = display_sta(sta)
        left_gap = max(data_left, x-r)
        right_gap = min(data_right, x+r)
        if left_gap > cursor:
            _line(msp, cursor, grade_rule_y, left_gap, grade_rule_y,
                  'GRADE_DISTANCE_RULE')
        cursor = max(cursor, right_gap)
    if cursor < data_right:
        _line(msp, cursor, grade_rule_y, data_right, grade_rule_y,
              'GRADE_DISTANCE_RULE')
    _line(msp, data_left, distance_rule_y, data_right, distance_rule_y,
          'GRADE_DISTANCE_RULE')
    for point in vip:
        if not (start - 1e-8 <= point.sta <= end + 1e-8):
            continue
        x = display_sta(point.sta)
        _line(msp, x, display_el(point.elevation), x, graph_bottom_y,
              'VIP_ANNOTATION')
        if point.kind.startswith('VIP') and start < point.sta < end:
            msp.add_circle((x, grade_rule_y), r, dxfattribs={'layer': 'VIP_MARKER'})
            _text(msp, f'{point.elevation:.{options.vip_elevation_decimals}f}',
                  x, grade_rule_y, min(options.text_height*.75, r*.65),
                  'VIP_MARKER', rotation=90)
            _text(msp, 'VC', x, grade_rule_y+r+options.text_height*.6,
                  options.text_height*.85, 'VIP_MARKER')

    ar = options.annotation_row_height
    for a, b in zip(vip, vip[1:]):
        left_sta = max(start, a.sta)
        right_sta = min(end, b.sta)
        if right_sta <= left_sta:
            continue
        midpoint = display_sta((left_sta + right_sta)/2)
        _text(msp, _fmt_grade(a.gradient_out, options.grade_decimals),
              midpoint, grade_rule_y + ar*.45,
              options.text_height*1.35, 'VIP_ANNOTATION')
        _text(msp, _fmt_distance(b.sta-a.sta),
              midpoint, distance_rule_y + ar*.45,
              options.text_height*.9, 'VIP_ANNOTATION')

    output.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temporary file, then replace. Never write to the input file.
    tmp = output.with_name(output.stem + '.tmp.dxf')
    try:
        doc.saveas(str(tmp))
        os.replace(tmp, output)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {
        'output': str(output), 'start': start, 'end': end,
        'vip_count': max(0, len(vip)-2), 'minor_grid_count': len(minor)-len(major),
        'major_grid_count': len(major), 'band_station_count': len(band_stations),
        'graph_bottom': graph_bottom, 'graph_bottom_y': graph_bottom_y,
        'origin_x': options.origin_x, 'origin_y': options.origin_y,
        'drawing_left': label_left, 'drawing_right': data_right,
        'grade_rule_y': grade_rule_y, 'distance_rule_y': distance_rule_y,
        'vip_circle_count': len(circle_stations),
        'vertical_scale': options.vertical_scale, 'vertical_exaggeration': factor,
    }


def main():
    parser = argparse.ArgumentParser(description='종단면도 final_result.dxf 생성 (1:1 설계 좌표)')
    parser.add_argument('source', help='converted_dxf.dxf')
    parser.add_argument('--output', help='결과 DXF 경로 (기본: 입력 폴더/final_result.dxf)')
    parser.add_argument('--grid', type=float, default=20, help='보조 그리드 간격(m)')
    parser.add_argument('--major', type=float, default=200, help='메인 그리드 간격(m)')
    parser.add_argument('--band-interval', type=float, default=20, help='밴드 수치 간격(m)')
    parser.add_argument('--origin-x', type=float, default=0.0)
    parser.add_argument('--origin-y', type=float, default=0.0)
    parser.add_argument('--graph-bottom', type=float, help='종단면도 하단 기준 표고(m)')
    args = parser.parse_args()
    src = Path(args.source)
    out = Path(args.output) if args.output else src.with_name('final_result.dxf')
    result = create_profile_drawing(src, out, DrawingOptions(
        station_interval=args.grid, major_interval=args.major,
        band_interval=args.band_interval, graph_bottom=args.graph_bottom,
        origin_x=args.origin_x, origin_y=args.origin_y))
    for key, val in result.items():
        print(f'{key}: {val}')


if __name__ == '__main__':
    main()
