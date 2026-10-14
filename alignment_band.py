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
    # At a simple curve BC/EC the offset is discontinuous: draw vertical jumps.
    vertices = [(station_x(points[0]), ybase + offset_at(points[0]))]
    for a,b in zip(points,points[1:]):
        middle=(a+b)/2
        # Segment interior decides which side of a discontinuity belongs to this interval.
        oa,ob=offset_at(a+min(1e-7,(b-a)/4)),offset_at(b-min(1e-7,(b-a)/4))
        pa=(station_x(a),ybase+oa); pb=(station_x(b),ybase+ob)
        if vertices[-1] != pa:
            vertices.append(pa)
        vertices.append(pb)
    final=(station_x(end),ybase+offset_at(end))
    if vertices[-1] != final:
        vertices.append(final)
    msp.add_lwpolyline(vertices,dxfattribs={'layer':'ALIGNMENT_CURVE'})
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
        text(msp,f"IP{ip['ip_no']}  IA={ip['ia']}  R={ip['radius_m']:g}",x,y1,1.8,'ALIGNMENT_IP_TEXT')
        text(msp,f"T.L={ip['tl_m']:.2f}  C.L={ip['cl_m']:.2f}",x,y2,1.8,'ALIGNMENT_IP_TEXT')
    return {'curve_count':len(ips),'curve_visible_count':visible,'curve_source':str(source),
            'curve_station_range':(ips[0]['curve_start_sta_m'],ips[-1]['curve_end_sta_m'])}
