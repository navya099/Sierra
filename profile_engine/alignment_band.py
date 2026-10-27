"""Render DXF-derived horizontal alignment in the 0..20 mm profile band.

Right: +6 mm, left: -6 mm. Cubic spiral transitions are linear
SP->PC and CP->PS; circular part PC->CP is constant offset.
"""
from pathlib import Path
from alignment_reader import extract_with_stations


def draw_alignment_band(msp, source, start, end, station_x, origin_y, text, line):
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f'평면선형 DXF가 없습니다: {source}')
    result = extract_with_stations(source)
    ips = result['ips']
    # Preserve source chainage; never stretch/rebase horizontal data to vertical range.
    ybase = origin_y + 10.0
    def offset_at(sta):
        for ip in ips:
            a, b = ip['curve_start_sta_m'], ip['curve_end_sta_m']
            if not a <= sta <= b:
                continue
            offset = ip['band_offset_mm']
            if ip['curve_type'] == 'simplecurve':
                return offset
            p, q = ip['stations']['PC'], ip['stations']['CP']
            if sta < p:
                return offset * (sta-a)/(p-a) if p>a else offset
            if sta <= q:
                return offset
            return offset * (b-sta)/(b-q) if b>q else offset
        return 0.0
    breaks = {start, end}
    visible = 0
    for ip in ips:
        a, b = ip['curve_start_sta_m'], ip['curve_end_sta_m']
        if b < start or a > end:
            continue
        visible += 1
        for station in ip['stations'].values():
            if start < station < end:
                breaks.add(station)
    points = sorted(breaks)
    # Preserve the approved diagram geometry while splitting entities by type.
    # Straight = red (ACI 1), curved = white (ACI 7).
    # The interval midpoint determines the color; exact element stations
    # are already included in `points`, so color changes occur at SP/PS or BC/EC.
    line_count = 0
    for a, b in zip(points, points[1:]):
        if b <= a:
            continue
        mid = (a + b) / 2.0
        curve_interval = any(
            ip['curve_start_sta_m'] <= mid <= ip['curve_end_sta_m']
            for ip in ips
        )
        epsilon = min(1e-7, (b - a) / 4.0)
        oa = offset_at(a + epsilon)
        ob = offset_at(b - epsilon)
        msp.add_line(
            (station_x(a), ybase + oa),
            (station_x(b), ybase + ob),
            dxfattribs={'layer': 'ALIGNMENT_CURVE' if curve_interval
                        else 'ALIGNMENT_STRAIGHT'}
        )
        line_count += 1

    # Simple curves have no spiral: connect the offset discontinuities
    # vertically in white, without modifying the existing shape.
    for ip in ips:
        if ip['curve_type'] != 'simplecurve':
            continue
        for sta in (ip['curve_start_sta_m'], ip['curve_end_sta_m']):
            if start <= sta <= end:
                msp.add_line(
                    (station_x(sta), ybase),
                    (station_x(sta), ybase + ip['band_offset_mm']),
                    dxfattribs={'layer': 'ALIGNMENT_CURVE'}
                )
                line_count += 1
    for ip in ips:
        a,b=ip['curve_start_sta_m'],ip['curve_end_sta_m']
        left,right=max(a,start),min(b,end)
        if right<=left:
            continue
        mid=(left+right)/2
        x=station_x(mid)
        # Text kept inside band, away from station row at Y=17.
        y1=origin_y+8.5 if ip['direction']=='LEFT' else origin_y+7.7
        y2=y1-2.6
        text(msp,f"IA={ip['ia']}  R={ip['radius_m']:g}",x,y1,1.8,'ALIGNMENT_IP_TEXT')
        text(msp,f"T.L={ip['tl_m']:.2f}  C.L={ip['cl_m']:.2f}",x,y2,1.8,'ALIGNMENT_IP_TEXT')
    # Curve-element labels: exact station X, compact labels inside the 0..20 band.
    # Labels retain their approved placement; no element tick/leader lines are drawn.
    station_label_count = 0
    for ip in ips:
        for name, sta in ip['stations'].items():
            if not start <= sta <= end:
                continue
            x = station_x(sta)
            # Right curves occupy the upper side of the baseline, so annotate below;
            # left curves occupy the lower side, so annotate above.
            is_right = ip['direction'] == 'RIGHT'
            # 3 mm toward the band interior from the actual curve diagram at this station.
            diagram_y = ybase + offset_at(sta)
            label_y = diagram_y + (-3.0 if is_right else 3.0)
            km = int(sta // 1000)
            metres = sta - km * 1000
            station_text = f'{name}={km}km{metres:06.2f}'
            # Left alignment avoids encroaching on the preceding interval.
            from ezdxf.enums import TextEntityAlignment
            entity = text(msp, station_text, x + 1.5, label_y, 2.4,
                          'ALIGNMENT_ELEMENT_TEXT')
            entity.set_placement((x + 1.5, label_y),
                                 align=TextEntityAlignment.LEFT)
            station_label_count += 1
    return {'curve_count':len(ips),'curve_visible_count':visible,'curve_source':str(source),
            'curve_station_range':(ips[0]['curve_start_sta_m'],ips[-1]['curve_end_sta_m']),
            'curve_element_label_count':station_label_count,'diagram_line_count':line_count}
