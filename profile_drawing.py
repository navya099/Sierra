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
from profile_datum import DatumConfig, DatumSegment, plan_datum_segments


@dataclass(frozen=True)
class DrawingOptions:
    station_interval: float = 20.0
    major_interval: float = 200.0
    band_interval: float = 20.0
    alignment_station_interval: float = 200.0  # 평면선형 밴드 측점 표기 간격(m)
    graph_bottom: float | None = None
    bottom_margin: float = 12.0
    band_row_height: float = 6.0
    label_column_width: float = 22.0
    text_height: float = 2.0
    include_alignment_placeholder: bool = True
    annotation_row_height: float = 6.0
    grade_decimals: int = 1
    distance_decimals: int = 2
    vip_circle_radius: float = 8.0
    vip_elevation_decimals: int = 2
    vertical_scale: float = 400.0  # 1:V, reference horizontal scale 1:1000
    horizontal_scale: float = 1000.0
    origin_x: float = 0.0
    origin_y: float = 0.0
    start_margin: float = 10.0  # output drawing units (mm)
    end_margin: float = 10.0    # output drawing units (mm)
    auto_datum: bool = True
    elevation_window_m: float = 60.0  # legacy compatibility; actual window derives from Y limits
    plot_lower_y: float = 150.0
    plot_upper_y: float = 250.0
    datum_step_m: float = 10.0
    datum_safety_margin_m: float = 5.0


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
    if not all(math.isfinite(v) and v >= 0 for v in (options.start_margin, options.end_margin)):
        raise ValueError('좌우 마진은 0 이상의 유한한 수여야 합니다.')
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

    # A datum change affects profile geometry only, never the band or stationing.
    layout = ProfileLayout(origin_x=options.origin_x, origin_y=options.origin_y)
    graph_base_y = layout.origin_y + options.plot_lower_y
    if options.auto_datum and options.graph_bottom is not None:
        raise ValueError('자동 표고 기준과 수동 graph_bottom을 동시에 사용할 수 없습니다.')
    if options.auto_datum:
        datum_config = DatumConfig(
            horizontal_scale=options.horizontal_scale,
            vertical_scale=options.vertical_scale,
            plot_lower_y=options.plot_lower_y,
            plot_upper_y=options.plot_upper_y,
            datum_step_m=options.datum_step_m,
            safety_margin_m=options.datum_safety_margin_m,
        )
        datum_segments = plan_datum_segments(ground_points, plan_points, datum_config)
    else:
        relevant = [start, end]
        relevant += [x for x, _ in ground_points if start < x < end]
        relevant += [x for x, _ in plan_points if start < x < end]
        lowest = min(min(ground.at(x)[0], plan.at(x)[0]) for x in relevant)
        graph_bottom = (lowest - options.bottom_margin if options.graph_bottom is None
                        else options.graph_bottom)
        if graph_bottom >= lowest:
            raise ValueError('수동 종단 기준 표고는 최저 표고보다 낮아야 합니다.')
        datum_segments = [DatumSegment(start, end, graph_bottom)]
    graph_bottom = datum_segments[0].datum_el

    def display_el(el, datum_el):
        return layout.elevation_y(el, datum_el, options.plot_lower_y,
                                  options.vertical_scale)

    def display_sta(sta):
        # Start/end margins are geometric whitespace, NOT extra railway stationing.
        return layout.station_x(sta, start, options.horizontal_scale) + options.start_margin
    graph_bottom_y = graph_base_y
    data_left = layout.data_left_x  # left band/grade-rule boundary
    data_right = display_sta(end) + options.end_margin  # right boundary
    actual_start_x = display_sta(start)
    actual_end_x = display_sta(end)
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
    _layer(doc, 'VIP_ANNOTATION', 1, 18)
    _layer(doc, 'GRADE_DISTANCE_RULE', 7, 18)
    _layer(doc, 'VIP_MARKER', 1, 18)
    _layer(doc, 'PROFILE_BAND', 7, 18)
    _layer(doc, 'BAND_TEXT', 7, 0)
    _layer(doc, 'DATUM_BREAK', 6, 18)
    _layer(doc, 'DATUM_LABEL', 7, 0)
    msp = doc.modelspace()

    def clipped(poly, fn, seg_start, seg_end):
        return ([(seg_start, fn.at(seg_start)[0])]
                + [(x, y) for x, y in poly if seg_start < x < seg_end]
                + [(seg_end, fn.at(seg_end)[0])])

    # Plan is always visible; ground is clipped to the paper-space graph window.
    from ezdxf.math import Vec2
    ylo = layout.origin_y + options.plot_lower_y
    yhi = layout.origin_y + options.plot_upper_y
    def clipped_ground_parts(vertices, datum):
        parts=[]; current=[]
        for (xa,ea),(xb,eb) in zip(vertices, vertices[1:]):
            ya=display_el(ea,datum); yb=display_el(eb,datum)
            t0,t1=0.0,1.0
            dy=yb-ya
            if abs(dy)<1e-12:
                if not (ylo<=ya<=yhi):
                    if len(current)>=2: parts.append(current)
                    current=[]
                    continue
            else:
                ta=(ylo-ya)/dy; tb=(yhi-ya)/dy
                t0=max(0.0,min(ta,tb));t1=min(1.0,max(ta,tb))
            if t1<t0-1e-10:
                if len(current)>=2: parts.append(current)
                current=[]
                continue
            a=(display_sta(xa+(xb-xa)*t0), ya+dy*t0)
            b=(display_sta(xa+(xb-xa)*t1), ya+dy*t1)
            if current and (abs(current[-1][0]-a[0])>1e-7 or abs(current[-1][1]-a[1])>1e-7):
                if len(current)>=2: parts.append(current)
                current=[]
            if not current: current=[a]
            if abs(a[0]-b[0])>1e-8 or abs(a[1]-b[1])>1e-8: current.append(b)
            if t1<1-1e-9:
                if len(current)>=2: parts.append(current)
                current=[]
        if len(current)>=2: parts.append(current)
        return parts
    for seg in datum_segments:
        pv=clipped(plan_points,raw_plan,seg.start_sta,seg.end_sta)
        msp.add_lwpolyline([(display_sta(x),display_el(y,seg.datum_el)) for x,y in pv],
                           dxfattribs={'layer':'PLAN_PROFILE'})
        gv=clipped(ground_points,raw_ground,seg.start_sta,seg.end_sta)
        if options.auto_datum:
            for part in clipped_ground_parts(gv,seg.datum_el):
                msp.add_lwpolyline(part,dxfattribs={'layer':'GROUND_PROFILE'})
        else:
            msp.add_lwpolyline([(display_sta(x), display_el(y,seg.datum_el)) for x,y in gv],
                               dxfattribs={'layer':'GROUND_PROFILE'})

    minor = _multiples(start, end, options.station_interval)
    major = _multiples(start, end, options.major_interval)
    major_set = set(major)

    # At exact cuts use the datum of the segment on the right.
    from bisect import bisect_right
    cut_stations = [seg.end_sta for seg in datum_segments[:-1]]
    def datum_at(sta):
        idx = bisect_right(cut_stations, sta)
        return datum_segments[min(idx, len(datum_segments)-1)].datum_el

    for sta in minor:
        if sta not in major_set:
            _line(msp, display_sta(sta), (max(ylo,min(yhi,display_el(raw_ground.at(sta)[0], datum_at(sta))))
                   if options.auto_datum else display_el(raw_ground.at(sta)[0], datum_at(sta))),
                  display_sta(sta), layout.origin_y + layout.band_top, 'GRID_MINOR')
    for sta in major:
        _line(msp, display_sta(sta), (max(ylo,min(yhi,display_el(raw_ground.at(sta)[0], datum_at(sta))))
                   if options.auto_datum else display_el(raw_ground.at(sta)[0], datum_at(sta))),
              display_sta(sta), layout.origin_y + layout.band_top, 'GRID_MAJOR')

    # The band remains continuous; datum change marker exists only above band.
    if options.auto_datum:
        for left, right in zip(datum_segments, datum_segments[1:]):
            x = display_sta(left.end_sta)
            y0 = layout.origin_y + layout.band_top
            y1 = yhi
            # Vertical break line with small zig-zag at the middle.
            ym = (y0 + y1) / 2
            points = [(x, y0), (x, ym-7), (x-2.5, ym-3),
                      (x+2.5, ym+3), (x, ym+7), (x, y1)]
            msp.add_lwpolyline(points, dxfattribs={'layer': 'DATUM_BREAK'})
            _text(msp, f'EL {left.datum_el:.0f}', x-11, y0+12,
                  2.4, 'DATUM_LABEL')
            _text(msp, f'EL {right.datum_el:.0f}', x+11, y0+12,
                  2.4, 'DATUM_LABEL')

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
    # 준공도면 평면선형 밴드: 200m마다 수평 측점 숫자 표시.
    # Datum 구간과 무관한 원래 측점 좌표를 사용한다.
    alignment_stations = _multiples(start, end, options.alignment_station_interval)
    if options.include_alignment_placeholder:
        for sta in alignment_stations:
            # 1km 정측점은 1km, 2km, ... ; 나머지는 200, 400, 600, 800.
            station_m = int(round(sta))
            station_label = (f'{station_m // 1000}km'
                             if station_m % 1000 == 0
                             else str(station_m % 1000))
            # 평면선형 밴드 상단(Y=20)에서 3mm 아래.
            _text(msp, station_label, display_sta(sta),
                  layout.origin_y + layout.alignment_top - 3.0,
                  layout.data_text_height, 'BAND_TEXT')
    # No internal vertical lines in the band: user-approved cleanup.

    circle_stations = sorted(p.sta for p in vip
                             if p.kind.startswith('VIP') and start < p.sta < end)
    r = options.vip_circle_radius
    # Grade/distance rules are inset inside the 10 mm margins.
    cursor = actual_start_x
    for sta in circle_stations:
        x = display_sta(sta)
        left_gap = max(actual_start_x, x-r)
        right_gap = min(actual_end_x, x+r)
        if left_gap > cursor:
            _line(msp, cursor, grade_rule_y, left_gap, grade_rule_y,
                  'GRADE_DISTANCE_RULE')
        cursor = max(cursor, right_gap)
    if cursor < actual_end_x:
        _line(msp, cursor, grade_rule_y, actual_end_x, grade_rule_y,
              'GRADE_DISTANCE_RULE')
    _line(msp, actual_start_x, distance_rule_y, actual_end_x, distance_rule_y,
          'GRADE_DISTANCE_RULE')
    for point in vip:
        if not (start - 1e-8 <= point.sta <= end + 1e-8):
            continue
        x = display_sta(point.sta)
        _line(msp, x, display_el(point.elevation, datum_at(point.sta)), x, top,
              'VIP_ANNOTATION')
        if point.kind.startswith('VIP') and start < point.sta < end:
            msp.add_circle((x, grade_rule_y), r, dxfattribs={'layer': 'VIP_MARKER'})
            _text(msp, f'{point.elevation:.{options.vip_elevation_decimals}f}',
                  x, grade_rule_y, 2.4,
                  'VIP_MARKER', rotation=90)
            _text(msp, 'VC', x, grade_rule_y+r+options.text_height*.6,
                  2.4, 'VIP_MARKER')

    ar = options.annotation_row_height
    for a, b in zip(vip, vip[1:]):
        left_sta = max(start, a.sta)
        right_sta = min(end, b.sta)
        if right_sta <= left_sta:
            continue
        midpoint = display_sta((left_sta + right_sta)/2)
        _text(msp, _fmt_grade(a.gradient_out, options.grade_decimals),
              midpoint, grade_rule_y + ar*.45,
              10.0, 'VIP_ANNOTATION')
        _text(msp, _fmt_distance(b.sta-a.sta),
              midpoint, distance_rule_y + ar*.45,
              5.0, 'VIP_ANNOTATION')

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
        'alignment_station_count': len(alignment_stations) if options.include_alignment_placeholder else 0,
        'graph_bottom': graph_bottom, 'graph_bottom_y': graph_bottom_y,
        'origin_x': options.origin_x, 'origin_y': options.origin_y,
        'drawing_left': label_left, 'drawing_right': data_right,
        'actual_start_x': actual_start_x, 'actual_end_x': actual_end_x,
        'start_margin': options.start_margin, 'end_margin': options.end_margin,
        'grade_rule_y': grade_rule_y, 'distance_rule_y': distance_rule_y,
        'vip_circle_count': len(circle_stations),
        'vertical_scale': options.vertical_scale, 'vertical_exaggeration': factor,
        'plot_lower_y': ylo, 'plot_upper_y': yhi,
        'datum_segment_count': len(datum_segments),
        'datum_break_count': len(datum_segments)-1,
        'datum_segments': [dict(start_sta=z.start_sta, end_sta=z.end_sta, datum_el=z.datum_el) for z in datum_segments],
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
    parser.add_argument('--start-margin', type=float, default=10.0, help='시작 여백(mm)')
    parser.add_argument('--end-margin', type=float, default=10.0, help='종료 여백(mm)')
    parser.add_argument('--graph-bottom', type=float, help='수동 모드에서만 사용')
    parser.add_argument('--no-auto-datum', action='store_true', help='자동 기준 표고 변경 끄기')
    parser.add_argument('--plot-lower-y', type=float, default=150.0)
    parser.add_argument('--plot-upper-y', type=float, default=250.0)
    parser.add_argument('--datum-step', type=float, default=10.0, help='기준 표고 단위(m)')
    parser.add_argument('--datum-margin', type=float, default=5.0, help='표고 창 상하 안전 여유(m)')
    args = parser.parse_args()
    src = Path(args.source)
    out = Path(args.output) if args.output else src.with_name('final_result.dxf')
    result = create_profile_drawing(src, out, DrawingOptions(
        station_interval=args.grid, major_interval=args.major,
        band_interval=args.band_interval, graph_bottom=args.graph_bottom,
        origin_x=args.origin_x, origin_y=args.origin_y,
        start_margin=args.start_margin, end_margin=args.end_margin,
        auto_datum=not args.no_auto_datum, plot_lower_y=args.plot_lower_y,
        plot_upper_y=args.plot_upper_y,
        datum_step_m=args.datum_step, datum_safety_margin_m=args.datum_margin))
    for key, val in result.items():
        print(f'{key}: {val}')


if __name__ == '__main__':
    main()
