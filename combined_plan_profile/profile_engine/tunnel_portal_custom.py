"""v12.5.5-D.2: user longitudinal portal DXF placement (rigid grade rotation).

Template: mm, origin (0,0) = tunnel design grade at junction.
Local +X points into the tunnel for the start portal; end portal mirrors X.
Source DXF is never modified. BLOCK INSERTs are recursively flattened.
"""
from pathlib import Path
import math
import ezdxf
from ezdxf import path as ezpath
from .tunnel_portal import _clip_x

def load_portal_template(filename, tolerance_mm=5.0):
    doc=ezdxf.readfile(str(filename))
    geometry=[]
    def visit(entity, depth=0):
        if depth > 12:
            raise ValueError('갱문 DXF 블록 중첩 깊이가 12를 초과합니다.')
        kind=entity.dxftype()
        if kind=='INSERT':
            for child in entity.virtual_entities():
                visit(child,depth+1)
            return
        if kind=='LINE':
            a,b=entity.dxf.start,entity.dxf.end
            pts=[(float(a.x),float(a.y)),(float(b.x),float(b.y))]
            closed=False
        elif kind=='LWPOLYLINE' and not any(abs(p[4])>1e-10 for p in entity.get_points('xyseb')):
            pts=[(float(p[0]),float(p[1])) for p in entity.get_points('xy')]
            closed=bool(entity.closed)
        elif kind=='POLYLINE' and not entity.is_3d_polyline and not entity.is_poly_face_mesh and not entity.is_polygon_mesh:
            pts=[(float(v.dxf.location.x),float(v.dxf.location.y)) for v in entity.vertices]
            closed=bool(entity.is_closed)
        elif kind in ('ARC','CIRCLE','ELLIPSE','SPLINE','LWPOLYLINE','POLYLINE'):
            try:
                pts=[(float(v.x),float(v.y)) for v in ezpath.make_path(entity).flattening(tolerance_mm)]
            except Exception as exc:
                raise ValueError(f'갱문 DXF {kind} 형상을 변환할 수 없습니다: {exc}') from exc
            closed=kind=='CIRCLE' or (kind=='LWPOLYLINE' and entity.closed)
        else:
            # Dimensions, annotations, hatch and other objects are intentionally
            # excluded from portal structural outlines.
            return
        if len(pts)<2 or any(not all(math.isfinite(v) for v in xy) for xy in pts):
            raise ValueError(f'갱문 DXF {kind} 객체 좌표가 올바르지 않습니다.')
        geometry.append((pts,closed))
    for entity in doc.modelspace():
        visit(entity)
    if not geometry:
        raise ValueError('갱문 DXF에서 LINE/폴리라인/곡선/블록 형상을 찾지 못했습니다.')
    return geometry

def _grade_at(elevation_at, sta):
    # Symmetric difference in actual metres, no print scaling involved.
    delta=0.05
    return math.atan2(elevation_at(sta+delta)-elevation_at(sta-delta),2*delta)

def transform_template(geometry,junction,direction,elevation_at,outer_top):
    if direction not in (-1,1):
        raise ValueError('갱문 방향은 -1 또는 +1이어야 합니다.')
    angle=_grade_at(elevation_at,junction)
    ca,sa=math.cos(angle),math.sin(angle)
    z0=elevation_at(junction)  # Custom DXF origin = tunnel design grade at junction
    # template x: negative = outside at tunnel start, positive = inside.
    # For end portal reverse local X. Rigid rotate in STA/EL before scaling.
    mirror=1 if direction==-1 else -1
    result=[]
    for pts,closed in geometry:
        placed=[]
        for x_mm,y_mm in pts:
            x=mirror*x_mm/1000.0
            y=y_mm/1000.0
            placed.append((junction+ca*x-sa*y,z0+sa*x+ca*y))
        result.append((placed,closed))
    return result

def draw_custom_profile_portals(msp,structures,filename,start,end,datum_segments,
                                elevation_at,display_sta,display_el,outer_top,
                                color=6):
    geometry=load_portal_template(filename)
    count=0
    for seg in structures:
        if seg.kind!='TUNNEL': continue
        for junction,direction in ((seg.start_sta,-1),(seg.end_sta,1)):
            for coords,closed in transform_template(geometry,junction,direction,elevation_at,outer_top):
                for datum in datum_segments:
                    lo=max(start,datum.start_sta)
                    hi=min(end,datum.end_sta)
                    if hi<=lo: continue
                    if closed:
                        visible=_clip_x(coords,lo,hi)
                        if len(visible)<3: continue
                    else:
                        # Split every segment at sheet/datum boundaries;
                        # never close an originally open LINE.
                        visible=[]
                        for a,b in zip(coords[:-1],coords[1:]):
                            dx=b[0]-a[0]
                            if abs(dx)<1e-12:
                                if lo<=a[0]<=hi: visible.append([a,b])
                                continue
                            t0=max(0.0,min((lo-a[0])/dx,(hi-a[0])/dx))
                            t1=min(1.0,max((lo-a[0])/dx,(hi-a[0])/dx))
                            if t1>t0:
                                visible.append([(a[0]+dx*t0,a[1]+(b[1]-a[1])*t0),
                                                (a[0]+dx*t1,a[1]+(b[1]-a[1])*t1)])
                        for line in visible:
                            msp.add_lwpolyline([(display_sta(s),display_el(z,datum.datum_el)) for s,z in line],
                                               dxfattribs={'layer':'TUNNEL_PORTAL'})
                            count+=1
                        continue
                    msp.add_lwpolyline([(display_sta(s),display_el(z,datum.datum_el)) for s,z in visible],
                                       close=True,dxfattribs={'layer':'TUNNEL_PORTAL'})
                    count+=1
    return count
