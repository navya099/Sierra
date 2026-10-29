"""v1.8-A: IP교점선만 원본 PLAN DXF에서 선택하여 A1 PLAN에 작도.
원본 파일, v1.7.2 작도 코드는 변경하지 않는다.
"""
from .combined_plan_profile_v1_6_core import PLAN_RECT, clip
import math


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
            seg=clip(ta,tb,PLAN_RECT)
            if seg is not None and math.dist(*seg)>1e-8:
                dst.add_line(*seg,dxfattribs={'layer':'IP라인'})
                counts['ip_alignment_drawn']+=1
            else: counts['ip_alignment_clipped']+=1
    print(f"[IP교점선] {sheet_start:.0f}~{sheet_end:.0f}m: {counts}; 좌표샘플={samples}",flush=True)
    return counts
