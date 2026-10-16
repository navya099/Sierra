"""Overlay vertical VIP grade symbols on the source horizontal alignment DXF.

Source DXFs are read-only; output is a new copy. Requires ezdxf.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
import math
from pathlib import Path
import ezdxf
from ezdxf.enums import TextEntityAlignment
from dxf_reader import extract_profile
from bridge_plan import draw_bridge_plan, BridgePlanSection
from bridge_plan_pier import draw_plan_piers, PlanPierSettings

LAYERS = ('PLAN_VIP_LINE', 'PLAN_GRADE_IN_LINE', 'PLAN_GRADE_OUT_LINE',
          'PLAN_GRADE_IN_TEXT', 'PLAN_GRADE_OUT_TEXT')

def read_fl(doc):
    matches = [e for e in doc.modelspace().query('LWPOLYLINE') if e.dxf.layer.casefold() == 'fl']
    if len(matches) != 1:
        raise ValueError(f'FL LWPOLYLINE must be exactly one (found {len(matches)})')
    ent = matches[0]
    if ent.closed or any(abs(b) > 1e-12 for _, _, b in ent.get_points('xyb')):
        raise ValueError('FL must be an open polyline without bulges')
    points = [(float(x), float(y)) for x,y in ent.get_points('xy')]
    if len(points)<2: raise ValueError('FL must have at least two vertices')
    clean=[points[0]]
    distances=[0.0]
    for b in points[1:]:
        length=math.dist(clean[-1],b)
        if length<1e-8: continue  # rounded FL vertices can repeat
        clean.append(b)
        distances.append(distances[-1]+length)
    return clean,distances

def position_at(sta, points, distances):
    if sta < -1e-6 or sta > distances[-1]+1e-6:
        raise ValueError(f'STA {sta:.3f} outside FL range 0..{distances[-1]:.3f}')
    sta=max(0,min(sta,distances[-1]))
    idx=min(bisect_right(distances,sta)-1,len(points)-2)
    a,b=points[idx],points[idx+1]
    dx,dy=b[0]-a[0],b[1]-a[1]
    seg=distances[idx+1]-distances[idx]
    t=(sta-distances[idx])/seg
    return (a[0]+dx*t,a[1]+dy*t),(dx/seg,dy/seg)

def fmt_grade(v):
    if abs(v)<1e-8: return 'L'
    display = f'{v:.1f}'
    if display in ('0.0', '-0.0'): return '0'
    return display.rstrip('0').rstrip('.')

def draw_symbol(msp, xy, tangent, grade_in, grade_out, *, stem=30., arm=10.5, text_height=3.):
    """Local x=forward tangent; local y=left normal. Stem from FL toward left.

    +grade is rising in forward station direction. Symbol angle is fixed +/-30 deg.
    """
    tx,ty=tangent; nx,ny=-ty,tx
    def tr(x,y): return (xy[0]+tx*x+nx*y,xy[1]+ty*x+ny*y)
    pivot=(0.,stem)
    msp.add_line(tr(0,0),tr(*pivot),dxfattribs={'layer':'PLAN_VIP_LINE'})
    angles=[(grade_in,'IN'),(grade_out,'OUT')]
    for grade,side in angles:
        angle=math.radians(30 if grade>1e-8 else -30 if grade < -1e-8 else 0)
        vx,vy=arm*math.cos(angle),arm*math.sin(angle)
        if side=='IN':
            start=(-vx,stem-vy);end=pivot
            text_xy=(-vx-0.8,stem-vy+1.0)
        else:
            start=pivot;end=(vx,stem+vy)
            # Anchor the right end of the text just before the arm endpoint.
            # Right alignment guarantees that even the last decimal digit
            # stays inside the OUT arm (independent of text length).
            ux,uy=math.cos(angle),math.sin(angle)
            text_xy=(vx-0.65*ux-0.65*uy,
                     stem+vy-0.65*uy+0.65*ux)
        msp.add_line(tr(*start),tr(*end),dxfattribs={'layer':f'PLAN_GRADE_{side}_LINE'})
        rotation=(math.degrees(math.atan2(ty,tx))+math.degrees(angle))%360
        label = msp.add_text(fmt_grade(grade),dxfattribs={
            'layer':f'PLAN_GRADE_{side}_TEXT','height':text_height,
            'rotation':rotation})
        if side == 'OUT':
            label.set_placement(tr(*text_xy), align=TextEntityAlignment.RIGHT)
        else:
            label.dxf.insert = tr(*text_xy)

def create_final_plan(plan_dxf, profile_dxf, output_dxf, *, station_origin=0., stem=30., arm=10.5, text_height=3., vips=None, structures=(), bridge_nominal_span=30., bridge_plan_section: BridgePlanSection | None = None, bridge_plan_pier_settings: PlanPierSettings | None = None):
    plan_dxf=Path(plan_dxf).resolve();profile_dxf=Path(profile_dxf).resolve();output_dxf=Path(output_dxf).resolve()
    if output_dxf in (plan_dxf,profile_dxf): raise ValueError('Output must differ from both source DXFs')
    if not all(math.isfinite(x) for x in (station_origin,stem,arm,text_height)) or min(stem,arm,text_height)<=0:
        raise ValueError('Invalid symbol dimensions')
    vips=[v for v in (extract_profile(profile_dxf) if vips is None else vips) if v.gradient_in is not None and v.gradient_out is not None]
    doc=ezdxf.readfile(plan_dxf)
    points,distances=read_fl(doc)
    if not vips: raise ValueError('No interior VIP points found')
    placements=[]
    for vip in vips:
        # Validate all stations before adding any output entities.
        xy,tangent=position_at(vip.sta-station_origin,points,distances)
        placements.append((vip,xy,tangent))
    for name in LAYERS:
        if name not in doc.layers: doc.layers.new(name,dxfattribs={'color':1})
        else: doc.layers.get(name).color=1
    msp=doc.modelspace()
    for vip,xy,tangent in placements:
        draw_symbol(msp,xy,tangent,vip.gradient_in,vip.gradient_out,stem=stem,arm=arm,text_height=text_height)
    draw_bridge_plan(msp, structures, points=points, distances=distances,
                     position_at=position_at, station_origin=station_origin,
                     nominal_span=bridge_nominal_span, section=bridge_plan_section)
    draw_plan_piers(msp, structures, points=points, distances=distances,
                    position_at=position_at, station_origin=station_origin,
                    nominal_span=bridge_nominal_span, settings=bridge_plan_pier_settings)
    output_dxf.parent.mkdir(parents=True,exist_ok=True)
    doc.saveas(output_dxf)
    return [{'sta':v.sta,'x':xy[0],'y':xy[1], 'grade_in':v.gradient_in,'grade_out':v.gradient_out} for v,xy,_ in placements]

def main():
    p=argparse.ArgumentParser(description='Apply vertical VIP symbols to horizontal plan DXF')
    p.add_argument('plan_dxf');p.add_argument('profile_dxf');p.add_argument('-o','--output',default='final_plan_result.dxf')
    p.add_argument('--station-origin',type=float,default=0.,help='FL start station in metres')
    args=p.parse_args()
    result=create_final_plan(args.plan_dxf,args.profile_dxf,args.output,station_origin=args.station_origin)
    for v in result: print(f"STA {v['sta']:.3f} -> ({v['x']:.3f}, {v['y']:.3f}) IN {fmt_grade(v['grade_in'])} OUT {fmt_grade(v['grade_out'])}")
    print(f'Wrote {args.output}: {len(result)} VIP symbols')
if __name__=='__main__':main()
