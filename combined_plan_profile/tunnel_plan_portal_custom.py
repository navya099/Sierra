"""D.4: place custom plan portal DXF rigidly at tunnel start/end (metres)."""
import math
from tunnel_portal_custom import load_portal_template

LAYER = 'TUNNEL_PORTAL_PLAN_CUSTOM'

def place_custom_portal(geometry, junction, direction, *, points, distances,
                        position_at, station_origin=0.0):
    """DXF origin -> alignment junction. Template +X points into tunnel at START.

    Source geometry in mm; +Y is left of forward alignment.
    At END the X coordinate is mirrored to point outside the tunnel.
    Only rigid placement: no alignment-curvature warping.
    """
    if direction not in (-1, 1):
        raise ValueError('갱문 방향은 -1 또는 +1이어야 합니다.')
    (cx,cy),(tx,ty)=position_at(junction-station_origin,points,distances)
    length=math.hypot(tx,ty)
    if length < 1e-12: raise ValueError('갱문 위치의 접선 벡터가 유효하지 않습니다.')
    tx,ty=tx/length,ty/length
    nx,ny=-ty,tx
    mirror=1 if direction == -1 else -1
    result=[]
    for vertices,closed in geometry:
        transformed=[]
        for x_mm,y_mm in vertices:
            x=mirror*x_mm/1000.0
            y=y_mm/1000.0
            transformed.append((cx+tx*x+nx*y,cy+ty*x+ny*y))
        result.append((transformed,closed))
    return result

def draw_custom_plan_portals(msp, structures, dxf_path, *, points, distances,
                             position_at, station_origin=0.0, color=6):
    geometry=load_portal_template(dxf_path)
    if LAYER not in msp.doc.layers:
        msp.doc.layers.new(LAYER,dxfattribs={'color':color})
    count=0
    for structure in structures:
        if structure.kind != 'TUNNEL': continue
        for sta,direction in ((structure.start_sta,-1),(structure.end_sta,1)):
            if not station_origin-1e-6 <= sta <= station_origin+distances[-1]+1e-6:
                raise ValueError(f'갱문 배치 STA가 선형 범위 밖입니다: {sta:.2f}')
            for coords,closed in place_custom_portal(
                geometry,sta,direction,points=points,distances=distances,
                position_at=position_at,station_origin=station_origin
            ):
                msp.add_lwpolyline(coords,close=closed,dxfattribs={'layer':LAYER})
                count+=1
    return count
