"""B.9 trial: reuse standalone plan structure engines; transform and clip to B.7 matchlines."""
import json
import math
from pathlib import Path
import ezdxf
from .bridge_plan import draw_bridge_plan, BridgePlanSection
from .bridge_plan_pier import draw_plan_piers, PlanPierSettings
from .bridge_plan_abutment import draw_plan_abutments
from .tunnel_plan import draw_tunnel_plan
from .tunnel_plan_portal import draw_plan_portals
from .tunnel_plan_portal_custom import draw_custom_plan_portals
from .structure_plan_label import draw_plan_structure_labels, PlanLabelSettings
from .profile_engine.structure_label import LabelSettings
from .profile_engine.tunnel_profile import TunnelSettings
from .profile_engine.tunnel_portal import PortalSettings
from .profile_engine.tunnel_section import load_tunnel_section
from .combined_plan_profile_v1_7_core import make_plan_matchline_polygon, clip_to_plan_polygon
from .combined_plan_profile_v1_7_core import position_at as position_xy


def _position(s, points, distances):
    from bisect import bisect_right
    if s < -1e-6 or s > distances[-1]+1e-6:
        raise ValueError(f'구조물 STA {s:g}가 FL 범위를 벗어났습니다')
    s=max(0,min(s,distances[-1]))
    i=min(bisect_right(distances,s)-1,len(points)-2)
    a,b=points[i],points[i+1]
    d=distances[i+1]-distances[i]
    t=(s-distances[i])/d
    return ((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t),((b[0]-a[0])/d,(b[1]-a[1])/d))


def build_structure_cache(structures,points,distances,station_origin,settings_path):
    """Generate source XY entities only once, independent of number of sheets."""
    cfg=json.loads(Path(settings_path).read_text(encoding='utf-8')) if settings_path else {}
    plan=cfg.get('plan',{})
    if not isinstance(plan,dict): raise ValueError('plan 설정은 JSON 객체여야 합니다')
    doc=ezdxf.new('R2013');msp=doc.modelspace()
    span=float(plan.get('bridge_nominal_span',30.))
    section=BridgePlanSection(**plan.get('bridge_section',{}))
    pier=PlanPierSettings(**plan.get('pier',{}))
    kw=dict(points=points,distances=distances,position_at=_position,station_origin=station_origin)
    draw_bridge_plan(msp,structures,nominal_span=span,section=section,**kw)
    draw_plan_piers(msp,structures,nominal_span=span,settings=pier,**kw)
    bridges=[s for s in structures if s.kind=='BRIDGE']
    if bridges and plan.get('bridge_abutment_plan_dxf'):
        draw_plan_abutments(msp,structures,template_path=plan['bridge_abutment_plan_dxf'],**kw)
    elif bridges:
        print('[B.9] 교대 평면 템플릿 경로 미지정: 교대 평면 작도 생략',flush=True)
    tunnels=[s for s in structures if s.kind=='TUNNEL']
    if tunnels:
        tc=cfg.get('tunnel',{}).copy()
        if 'section_dxf' in tc:tc['section']=load_tunnel_section(tc.pop('section_dxf'))
        ts=TunnelSettings(**tc);ts.validate()
        draw_tunnel_plan(msp,structures,section=ts.section,sample_step=ts.sample_step,lining_thickness=ts.lining_thickness,**kw)
        portal=PortalSettings(**cfg.get('portal',{}))
        if portal.plan_custom_dxf:
            draw_custom_plan_portals(msp,structures,portal.plan_custom_dxf,color=portal.color,**kw)
        else:
            # Built-in portal may exceed total FL extents; skip only if unsupported.
            try: draw_plan_portals(msp,structures,portal,sl_width=portal.sl_width,**kw)
            except ValueError as exc: print(f'[B.9] 기본 갱문 생략: {exc}',flush=True)
    if plan.get('labels_enabled',True):
        draw_plan_structure_labels(msp,structures,PlanLabelSettings(**plan.get('label',{})),LabelSettings(**cfg.get('label',{})),**kw)
    print(f'[B.9] 원본 평면 구조물 객체 {len(msp)}개 생성',flush=True)
    return doc


def _inside(p,edge,eps=1e-8):
    a,b=edge
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]) >= -eps

def _intersection(p,q,a,b):
    vx,vy=q[0]-p[0],q[1]-p[1]
    wx,wy=b[0]-a[0],b[1]-a[1]
    denom=vx*wy-vy*wx
    if abs(denom)<1e-14:return q
    t=((a[0]-p[0])*wy-(a[1]-p[1])*wx)/denom
    return (p[0]+t*vx,p[1]+t*vy)

def _clip_polygon(points,frame):
    result=list(points)
    for a,b in zip(frame,frame[1:]+frame[:1]):
        if not result:break
        out=[]
        for p,q in zip(result[-1:]+result[:-1],result):
            pi,qi=_inside(p,(a,b)),_inside(q,(a,b))
            if pi != qi:out.append(_intersection(p,q,a,b))
            if qi:out.append(q)
        result=out
    return result

def _open_segments(points,edges):
    for a,b in zip(points[:-1],points[1:]):
        seg=clip_to_plan_polygon(a,b,edges)
        if seg and math.dist(*seg)>1e-7:yield seg


def render_structure_sheet(doc,source_doc,transform,start,end,station_origin,points,distances):
    frame,edges=make_plan_matchline_polygon(start,end,station_origin,points,distances,transform)
    msp=doc.modelspace()
    counts={'closed':0,'open':0,'circle':0,'text':0}
    for layer in source_doc.layers:
        name=layer.dxf.name
        if name not in doc.layers:doc.layers.new(name,dxfattribs={'color':layer.dxf.color})
    if 'KOREAN' not in doc.styles:doc.styles.new('KOREAN',dxfattribs={'font':'txt.shx'})
    # transform() scales model metres to sheet mm; determine uniform scale from 1m step
    o=transform((0.,0.));u=transform((1.,0.));scale=math.dist(o,u)
    rot=math.degrees(math.atan2(u[1]-o[1],u[0]-o[0]))
    for ent in source_doc.modelspace():
        kind=ent.dxftype();layer=ent.dxf.layer
        if kind=='LWPOLYLINE':
            xy=[transform((x,y)) for x,y in ent.get_points('xy')]
            if ent.closed:
                poly=_clip_polygon(xy,frame)
                if len(poly)>=3:
                    msp.add_lwpolyline(poly,close=True,dxfattribs={'layer':layer});counts['closed']+=1
            else:
                for seg in _open_segments(xy,edges):
                    msp.add_lwpolyline(seg,dxfattribs={'layer':layer});counts['open']+=1
        elif kind=='LINE':
            a=transform(tuple(ent.dxf.start)[:2]);b=transform(tuple(ent.dxf.end)[:2])
            seg=clip_to_plan_polygon(a,b,edges)
            if seg:
                msp.add_line(*seg,dxfattribs={'layer':layer});counts['open']+=1
        elif kind=='CIRCLE':
            c=ent.dxf.center;r=ent.dxf.radius
            xy=[transform((c.x+r*math.cos(i*math.tau/72),c.y+r*math.sin(i*math.tau/72))) for i in range(72)]
            poly=_clip_polygon(xy,frame)
            if len(poly)>=3:
                msp.add_lwpolyline(poly,close=True,dxfattribs={'layer':layer});counts['circle']+=1
        elif kind=='TEXT':
            at=transform(tuple(ent.dxf.insert)[:2])
            if all(_inside(at,(a,b)) for a,b in zip(frame,frame[1:]+frame[:1])):
                txt=msp.add_text(ent.dxf.text,dxfattribs={'layer':layer,'height':ent.dxf.height*scale,
                    'rotation':(ent.dxf.get('rotation',0.)+rot)%360,'style':ent.dxf.get('style','Standard')})
                txt.dxf.insert=at
                counts['text']+=1
    return counts
