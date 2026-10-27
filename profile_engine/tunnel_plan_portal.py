"""v12.5.5-D.3: rectangular plan portal and inward-trimmed half ellipse.
Reference: 평면터널갱문.dxf. Geometry in real plan metres.
"""
import math

LAYER='TUNNEL_PORTAL_PLAN'

def portal_plan_vertices(junction, direction, sl_length, sl_width, points, distances,
                         position_at, station_origin=0.0, arc_segments=48):
    """Return box outline and half ellipse (separate open polylines).

    junction: station of tunnel entrance/exit. direction=-1 at start, +1 at end.
    At outer end s=junction+direction*SL_LENGTH, the semicircle bends
    inward toward the tunnel by SL_LENGTH*0.375 (as supplied DXF: 7.5/20).
    """
    if direction not in (-1,1): raise ValueError('갱문 방향이 올바르지 않습니다.')
    if not all(math.isfinite(v) and v>0 for v in (sl_length,sl_width)):
        raise ValueError('SL_LENGTH, SL_WIDTH는 양수여야 합니다.')
    if arc_segments<8:raise ValueError('반타원 분할 수는 8 이상이어야 합니다.')
    tip=junction+direction*sl_length
    def offset(sta,normal):
        (x,y),(tx,ty)=position_at(sta-station_origin,points,distances)
        return (x-ty*normal,y+tx*normal)
    half=sl_width/2
    # Four-sided box, matching the five reference LINEs, with shared start.
    box=[offset(junction,0),offset(junction,half),offset(tip,half),
         offset(tip,-half),offset(junction,-half),offset(junction,0)]
    # Semicircle starts at outer upper corner, bows inward, ends at lower corner.
    # The uploaded reference uses ellipse semi-axis along station = 7.5m
    # when SL_LENGTH=20m, i.e. 0.375 * SL_LENGTH.
    a=0.375*sl_length
    arc=[]
    for i in range(arc_segments+1):
        theta=math.pi/2-math.pi*i/arc_segments
        sta=tip-direction*a*math.cos(theta)
        lateral=half*math.sin(theta)
        arc.append(offset(sta,lateral))
    return box,arc

def draw_plan_portals(msp,structures,portal,*,points,distances,position_at,station_origin=0.0,sl_width=6.0):
    portal.validate()
    if LAYER not in msp.doc.layers:
        msp.doc.layers.new(LAYER,dxfattribs={'color':portal.color})
    count=0
    for structure in structures:
        if structure.kind!='TUNNEL':continue
        for sta,direction in ((structure.start_sta,-1),(structure.end_sta,1)):
            tip=sta+direction*portal.portal_length
            if min(sta,tip)<station_origin-1e-6 or max(sta,tip)>station_origin+distances[-1]+1e-6:
                raise ValueError(f'갱문 평면 범위가 선형 범위 밖입니다: STA {sta:.2f}')
            box,arc=portal_plan_vertices(sta,direction,portal.portal_length,sl_width,
                points,distances,position_at,station_origin)
            msp.add_lwpolyline(box,dxfattribs={'layer':LAYER})
            msp.add_lwpolyline(arc,dxfattribs={'layer':LAYER})
            count+=1
    return count
