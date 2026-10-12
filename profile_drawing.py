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
    vip_circle_radius: float = 4
    vip_elevation_decimals: int = 2
    vertical_scale: float = 400.0  # 1:V, reference horizontal scale 1:1000
    horizontal_scale: float = 1000.0


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
    negative = False
    if metres < 0:
        negative = True
        metres = abs(metres)

    km = int(metres) // 1000
    remainder = "{:.2f}".format(metres % 1000)
    formatted_distance = "{:d}km{:06.2f}".format(km, float(remainder))

    if negative:
        formatted_distance = "-" + formatted_distance

    return formatted_distance

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

    # Vertical exaggeration affects only the plotted geometry above the
    # profile baseline. Annotation rows and band heights stay readable.
    factor = options.horizontal_scale / options.vertical_scale
    def display_el(el):
        return graph_bottom + (el - graph_bottom) * factor
    ground_display = [(x, display_el(y)) for x, y in ground_points]
    plan_display = [(x, display_el(y)) for x, y in plan_points]
    ground = PiecewiseLinear(ground_display)
    plan = PiecewiseLinear(plan_display)

    doc = ezdxf.new('R2010')
    doc.header['$INSUNITS'] = 6  # meters
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

    # Clip line geometry at the common station limits.
    def clipped(poly, fn):
        return [(start, fn.at(start)[0])] + [(x, y) for x, y in poly if start < x < end] + [(end, fn.at(end)[0])]

    msp.add_lwpolyline(clipped(ground_display, ground), dxfattribs={'layer': 'GROUND_PROFILE'})
    msp.add_lwpolyline(clipped(plan_display, plan), dxfattribs={'layer': 'PLAN_PROFILE'})

    minor = _multiples(start, end, options.station_interval)
    major = _multiples(start, end, options.major_interval)
    for sta in minor:
        if any(math.isclose(sta, m, abs_tol=1e-7) for m in major):
            continue
        _line(msp, sta, ground.at(sta)[0], sta, graph_bottom, 'GRID_MINOR')
    for sta in major:
        _line(msp, sta, ground.at(sta)[0], sta, graph_bottom, 'GRID_MAJOR')

    # Five bands: four populated, alignment reserved for future horizontal geometry.
    names = ['절토고', '성토고', '지반고', '계획고']
    if options.include_alignment_placeholder:
        names.append('평면선형')
    rh = options.band_row_height
    n = len(names)
    left = start - options.label_column_width
    # Dedicated horizontal rules for grade and segment distance, like the
    # submitted engineering drawing. They do not change the 1:1 design coords.
    ar = options.annotation_row_height
    grade_rule_y = graph_bottom - ar
    distance_rule_y = graph_bottom - 2 * ar
    top = graph_bottom - 3 * ar
    bottom = top - n * rh
    # The upper horizontal rule is interrupted by VIP circles, so that it
    # never cuts through the elevation text. The lower distance rule is whole.
    circle_stations = sorted(p.sta for p in vip
                             if p.kind.startswith('VIP') and start < p.sta < end)
    r = options.vip_circle_radius
    cursor = start
    for sta in circle_stations:
        left_gap = max(start, sta - r)
        right_gap = min(end, sta + r)
        if left_gap > cursor:
            _line(msp, cursor, grade_rule_y, left_gap, grade_rule_y, 'GRADE_DISTANCE_RULE')
        cursor = max(cursor, right_gap)
    if cursor < end:
        _line(msp, cursor, grade_rule_y, end, grade_rule_y, 'GRADE_DISTANCE_RULE')
    _line(msp, start, distance_rule_y, end, distance_rule_y, 'GRADE_DISTANCE_RULE')
    # The circular VIP callout is a symbol, not a vertical-curve calculation.
    # No ordinate (종거) values are generated until vertical curves are supported.
    for point in vip:
        if point.kind.startswith('VIP') and start < point.sta < end:
            msp.add_circle((point.sta, grade_rule_y), r,
                           dxfattribs={'layer': 'VIP_MARKER'})
            _text(msp, f'{point.elevation:.{options.vip_elevation_decimals}f}',
                  point.sta, grade_rule_y, min(options.text_height * .75, r * .65),
                  'VIP_MARKER', rotation=90)
            _text(msp, 'VC', point.sta, grade_rule_y + r + options.text_height * .6,
                  options.text_height * .85, 'VIP_MARKER')
    for j in range(n + 1):
        y = top - j * rh
        _line(msp, left, y, end, y, 'PROFILE_BAND')#수평선
    for x in (left, start, end):
        _line(msp, x, top, x, bottom, 'PROFILE_BAND')
    for j, name in enumerate(names):
        _text(msp, name, (left + start) / 2, top - (j + .5) * rh,
              min(options.text_height, rh * .55), 'BAND_TEXT')

    band_stations = sorted(set(_multiples(start, end, options.band_interval) + [start, end]))
    for sta in band_stations:
        if sta != start and sta != end:
            pass#밴드 내부 수직 그리드 제거
        g = raw_ground.at(sta)[0]
        p = raw_plan.at(sta)[0]
        cut = max(g - p, 0)
        fill = max(p - g, 0)
        vals = [cut, fill, g, p]
        for j, value in enumerate(vals):
            # Vertical text follows the sample drawing, with enough room at 20m spacing.
            # Leave the inapplicable earthwork cell empty (not a dash or zero).
            if j < 2 and value <= 1e-7:
                continue
            _text(msp, f'{value:.2f}',
                  sta, top - (j + .5) * rh,
                  min(options.text_height, rh * .36), 'BAND_TEXT', rotation=90)

    # VIP elevations and entering/leaving grades.
    # Grade labels are placed over each segment to reduce clutter at vertices.
    for point in vip:
        if not (start - 1e-8 <= point.sta <= end + 1e-8):
            continue
        _line(msp, point.sta, display_el(point.elevation), point.sta, graph_bottom, 'VIP_ANNOTATION')

    # One grade and one distance label per constant-grade segment.
    # Both labels sit on horizontal rules, independent of ground elevation.
    for a, b in zip(vip, vip[1:]):
        left_sta = max(start, a.sta)
        right_sta = min(end, b.sta)
        if right_sta <= left_sta:
            continue
        midpoint = (left_sta + right_sta) / 2
        _text(msp, _fmt_grade(a.gradient_out, options.grade_decimals),
              midpoint, grade_rule_y + ar * .45,
              options.text_height * 1.35, 'VIP_ANNOTATION')
        _text(msp, _fmt_distance(b.sta - a.sta),
              midpoint, distance_rule_y + ar * .45,
              options.text_height * .9, 'VIP_ANNOTATION')

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
        'graph_bottom': graph_bottom,
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
    parser.add_argument('--graph-bottom', type=float, help='종단면도 하단 기준 표고(m)')
    args = parser.parse_args()
    src = Path(args.source)
    out = Path(args.output) if args.output else src.with_name('final_result.dxf')
    result = create_profile_drawing(src, out, DrawingOptions(
        station_interval=args.grid, major_interval=args.major,
        band_interval=args.band_interval, graph_bottom=args.graph_bottom))
    for key, val in result.items():
        print(f'{key}: {val}')


if __name__ == '__main__':
    main()
