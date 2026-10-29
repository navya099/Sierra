"""v1.8-A: IP교점선만 원본 PLAN DXF에서 선택하여 A1 PLAN에 작도.
원본 파일, v1.7.2 작도 코드는 변경하지 않는다.
"""
from .combined_plan_profile_v1_6_core import PLAN_RECT, clip
from .plan_entities_v1_7 import _station_of_point
import math


def render_ip_lines(source_doc, target_doc, transform, *,
                    sheet_start, sheet_end, fl_points, fl_distances,
                    station_origin=0., tolerance=1e-5):
    src=source_doc.modelspace(); dst=target_doc.modelspace()
    # IP라인의 꼭짓점(교점)으로 각 IP교점선의 소속 IP를 판정한다.
    ip_vertices=[]
    for ent in src:
        if ent.dxf.layer.casefold() != 'ip라인':
            continue
        if ent.dxftype()=='LWPOLYLINE':
            ip_vertices.extend(tuple(p) for p in ent.get_points('xy'))
        elif ent.dxftype()=='POLYLINE':
            ip_vertices.extend(tuple(v.dxf.location)[:2] for v in ent.vertices)
    ip_vertices=ip_vertices[1:-1] if len(ip_vertices)>=3 else ip_vertices
    if 'IP교점선' not in target_doc.layers:
        source_layer=source_doc.layers.get('IP교점선') if 'IP교점선' in source_doc.layers else None
        color=source_layer.dxf.get('color',1) if source_layer is not None else 1
        target_doc.layers.new('IP교점선',dxfattribs={'color':color})
    counts={'drawn':0,'skipped_station':0,'skipped_frame':0}
    for ent in src:
        if ent.dxf.layer.casefold() != 'ip교점선' or ent.dxftype()!='LINE':
            continue
        a=(ent.dxf.start.x,ent.dxf.start.y)
        b=(ent.dxf.end.x,ent.dxf.end.y)
        mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
        # IP라인의 교점 좌표를 기준으로 시트 소속 측점을 판단.
        # IP라인이 없는 DXF에서는 선분 중점의 FL 투영 측점을 대체 사용.
        anchor=min(ip_vertices,key=lambda p:math.dist(p,mid)) if ip_vertices else mid
        sta,_=_station_of_point(anchor,fl_points,fl_distances,station_origin)
        if sta is None or sta<sheet_start-tolerance or sta>sheet_end+tolerance:
            counts['skipped_station']+=1;continue
        clipped=clip(transform(a),transform(b),PLAN_RECT)
        if clipped is None or math.dist(*clipped)<1e-8:
            counts['skipped_frame']+=1;continue
        attrs={'layer':'IP교점선'}
        if ent.dxf.hasattr('color'):attrs['color']=ent.dxf.color
        if ent.dxf.hasattr('linetype') and ent.dxf.linetype in target_doc.linetypes:
            attrs['linetype']=ent.dxf.linetype
        dst.add_line(*clipped,dxfattribs=attrs)
        counts['drawn']+=1
    return counts
