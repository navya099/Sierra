"""v1.8-A: IP교점선만 원본 PLAN DXF에서 선택하여 A1 PLAN에 작도.
원본 파일, v1.7.2 작도 코드는 변경하지 않는다.
"""
from .combined_plan_profile_v1_6_core import PLAN_RECT, clip
from .combined_plan_profile_v1_7_core import position_at
import math


def _clip_halfplane(a, b, origin, tangent, keep_positive):
    """Clip segment to station boundary normal to FL tangent."""
    sign = 1.0 if keep_positive else -1.0
    f0 = sign * ((a[0]-origin[0])*tangent[0]+(a[1]-origin[1])*tangent[1])
    f1 = sign * ((b[0]-origin[0])*tangent[0]+(b[1]-origin[1])*tangent[1])
    if f0 < -1e-9 and f1 < -1e-9: return None
    if f0 >= -1e-9 and f1 >= -1e-9: return a,b
    t = f0/(f0-f1)
    mid=(a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1]))
    return (mid,b) if f0 < 0 else (a,mid)


def _tangent_at(sta, points, distances, station_origin):
    from bisect import bisect_right
    s=max(0.,min(sta-station_origin,distances[-1]))
    i=max(0,min(bisect_right(distances,s)-1,len(points)-2))
    a,b=points[i],points[i+1]
    d=math.dist(a,b)
    return ((b[0]-a[0])/d,(b[1]-a[1])/d)


def render_ip_lines(source_doc, target_doc, transform, *,
                    sheet_start, sheet_end, fl_points, fl_distances,
                    station_origin=0., tolerance=1e-5):
    src=source_doc.modelspace(); dst=target_doc.modelspace()
    # v1.8-A.1: IP는 FL 위에 있지 않으므로 IP 꼭짓점 투영 측점으로
    # 시트를 선별하지 않는다. 변환된 선분과 PLAN 도각의 교차만 판정한다.
    if 'IP교점선' not in target_doc.layers:
        source_layer=source_doc.layers.get('IP교점선') if 'IP교점선' in source_doc.layers else None
        color=source_layer.dxf.get('color',1) if source_layer is not None else 1
        target_doc.layers.new('IP교점선',dxfattribs={'color':color})
    # Actual connected IP alignment is an LWPOLYLINE on layer IP라인.
    if 'IP라인' not in target_doc.layers:
        layer=source_doc.layers.get('IP라인') if 'IP라인' in source_doc.layers else None
        target_doc.layers.new('IP라인',dxfattribs={'color':layer.dxf.get('color',7) if layer is not None else 7})
    counts={'drawn':0,'skipped_station':0,'skipped_frame':0,'ip_alignment_drawn':0,'ip_alignment_clipped':0}
    samples=[]
    for ent in src:
        if ent.dxf.layer.casefold() != 'ip교점선' or ent.dxftype()!='LINE':
            continue
        a=(ent.dxf.start.x,ent.dxf.start.y)
        b=(ent.dxf.end.x,ent.dxf.end.y)
        ta,tb=transform(a),transform(b)
        clipped=clip(ta,tb,PLAN_RECT)
        if len(samples)<3:
            samples.append((ent.dxf.handle,tuple(round(x,2) for x in ta),tuple(round(x,2) for x in tb),clipped is not None))
        if clipped is None or math.dist(*clipped)<1e-8:
            counts['skipped_frame']+=1;continue
        attrs={'layer':'IP교점선'}
        if ent.dxf.hasattr('color'):attrs['color']=ent.dxf.color
        if ent.dxf.hasattr('linetype') and ent.dxf.linetype in target_doc.linetypes:
            attrs['linetype']=ent.dxf.linetype
        dst.add_line(*clipped,dxfattribs=attrs)
        counts['drawn']+=1
    # Station boundaries are planes perpendicular to FL at exact sheet limits.
    # Unlike rectangular frame clipping, these stop IP alignment at the same
    # longitudinal stations as FL, even when the IP line is offset from FL.
    start_point=transform(position_at(sheet_start-station_origin,fl_points,fl_distances))
    end_point=transform(position_at(sheet_end-station_origin,fl_points,fl_distances))
    def transformed_tangent(sta):
        p=position_at(sta-station_origin,fl_points,fl_distances)
        u=_tangent_at(sta,fl_points,fl_distances,station_origin)
        q=transform((p[0]+u[0],p[1]+u[1]))
        o=transform(p)
        d=math.dist(q,o)
        return ((q[0]-o[0])/d,(q[1]-o[1])/d)
    start_tangent=transformed_tangent(sheet_start)
    end_tangent=transformed_tangent(sheet_end)
    counts['ip_alignment_station_clipped']=0
    # Transform and clip each connected IP-line segment individually.
    # Do not use IP vertex projected station: an IP is off the FL centerline.
    for ent in src:
        if ent.dxf.layer.casefold()!='ip라인': continue
        if ent.dxftype()=='LWPOLYLINE':
            vertices=[(float(x),float(y)) for x,y in ent.get_points('xy')]
            if ent.closed and vertices: vertices.append(vertices[0])
        elif ent.dxftype()=='LINE':
            vertices=[(ent.dxf.start.x,ent.dxf.start.y),(ent.dxf.end.x,ent.dxf.end.y)]
        else: continue
        for a,b in zip(vertices,vertices[1:]):
            ta,tb=transform(a),transform(b)
            seg=_clip_halfplane(ta,tb,start_point,start_tangent,True)
            if seg is not None:
                seg=_clip_halfplane(*seg,end_point,end_tangent,False)
            if seg is None:
                counts['ip_alignment_station_clipped']+=1
                continue
            seg=clip(*seg,PLAN_RECT)
            if seg is not None and math.dist(*seg)>1e-8:
                dst.add_line(*seg,dxfattribs={'layer':'IP라인'})
                counts['ip_alignment_drawn']+=1
            else: counts['ip_alignment_clipped']+=1
    print(f"[IP교점선] {sheet_start:.0f}~{sheet_end:.0f}m: {counts}; 좌표샘플={samples}",flush=True)
    return counts
