"""v1.7: copy station/curve annotations from source PLAN DXF into sheet-local PLAN area.
Does not mutate source entities. Coordinates are DXF XY (already civil XY swapped by producer).
"""
import math
import re
from .plan_ip_lines_v1_8a import _clip_halfplane, _tangent_at
from .combined_plan_profile_v1_7_core import position_at
from ezdxf import bbox
from .combined_plan_profile_v1_6_core import PLAN_RECT, clip

DEFAULT_LAYERS = ('km심볼','200심볼','km문자','200문자','보조측점','곡선인출선','곡선제원문자','IP교점선','IP문자')

def _inside(p, rect=PLAN_RECT, margin=0):
    return rect[0]+margin <= p[0] <= rect[2]-margin and rect[1]+margin <= p[1] <= rect[3]-margin

def _station_of_point(point, points, distances, station_origin):
    """Project a source DXF XY point onto FL and return (absolute station, offset)."""
    px, py = point[0], point[1]
    best_station, best_d2 = None, float('inf')
    for i, (a, b) in enumerate(zip(points, points[1:])):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length2 = dx*dx+dy*dy
        if length2 < 1e-16: continue
        t = max(0., min(1., ((px-a[0])*dx+(py-a[1])*dy)/length2))
        qx, qy = a[0]+t*dx, a[1]+t*dy
        d2 = (px-qx)**2+(py-qy)**2
        if d2 < best_d2:
            best_station = station_origin + distances[i] + t*(distances[i+1]-distances[i])
            best_d2 = d2
    return best_station, math.sqrt(best_d2)

_CURVE_STA = re.compile(r"(?i)\b(?:BC|EC|SP|PC|CP|PS|BTC|ETC|BCC|ECC|KA|KE|TS|SC|CS|ST)\s*[:=]\s*(?:(\d+)\s*km\s*)?(\d+(?:\.\d+)?)")

def _curve_text_station(value):
    """Parse v9 labels such as EC=0km552.23 and BC=1km047.51."""
    match = _CURVE_STA.search(value)
    if not match:
        return None
    km, meters = match.groups()
    return (int(km) * 1000 if km is not None else 0) + float(meters)

def _sheet_matchlines(transform, sheet_start, sheet_end, points, distances, origin):
    result=[]
    for sta in (sheet_start,sheet_end):
        source=position_at(sta-origin,points,distances)
        direction=_tangent_at(sta,points,distances,origin)
        a=transform(source)
        b=transform((source[0]+direction[0],source[1]+direction[1]))
        length=math.dist(a,b)
        result.append((a,((b[0]-a[0])/length,(b[1]-a[1])/length)))
    return result

def render_plan_entities(source_doc, target_doc, transform, angle_rad, horizontal_scale,
                         layers=DEFAULT_LAYERS, *, sheet_start=None, sheet_end=None,
                         fl_points=None, fl_distances=None, station_origin=0., station_cache=None):
    """Transform selected DXF modelspace entities; clip LINE, reject out-of-frame labels/symbols.
    Source entities in IP_Block_* are deliberately excluded: their absolute block coordinates
    and zero insertion require a separate safe block handler.
    """
    src=source_doc.modelspace(); dst=target_doc.modelspace()
    k=1000.0/horizontal_scale
    counts={'LINE':0,'TEXT':0,'MTEXT':0,'CIRCLE':0,'skipped':0, 'curve_text_station_excluded':0, 'curve_text_frame_excluded':0, 'curve_leader_station_excluded':0, 'curve_leader_matchline_clipped':0, 'curve_leader_drawn':0}
    selected={name.casefold() for name in layers}
    matchlines = (_sheet_matchlines(transform,sheet_start,sheet_end,fl_points,fl_distances,station_origin)
                  if fl_points is not None and sheet_start is not None and sheet_end is not None else None)
    for e in src:
        layer=e.dxf.get('layer','0')
        if layer.casefold() not in selected: continue
        typ=e.dxftype()
        if layer not in target_doc.layers:
            orig=source_doc.layers.get(layer) if layer in source_doc.layers else None
            target_doc.layers.new(layer,dxfattribs={'color':orig.dxf.get('color',7) if orig is not None else 7})
        attrs={'layer':layer}
        if e.dxf.hasattr('color'): attrs['color']=e.dxf.color
        # v1.7.2: 1km/200m markers and text are selected by FL station,
        # not by their transformed location inside the PLAN frame.
        station_layers = {'km심볼', '200심볼', 'km문자', '200문자'}
        if layer.casefold() in {name.casefold() for name in station_layers} and fl_points is not None:
            if typ == 'CIRCLE':
                anchor = e.dxf.center
            elif typ in ('TEXT', 'MTEXT'):
                anchor = e.dxf.insert
            else:
                anchor = None
            if anchor is not None:
                sta, offset = station_cache[e.dxf.handle] if station_cache is not None else _station_of_point(anchor, fl_points, fl_distances, station_origin)
                if (sta is None or offset > 2.0 or
                    (sheet_start is not None and sta < sheet_start-1e-5) or
                    (sheet_end is not None and sta > sheet_end+1e-5)):
                    counts['skipped'] += 1
                    continue
        if typ=='TEXT' and layer.casefold() == '곡선제원문자'.casefold():
            sta=_curve_text_station(e.dxf.text)
            if sta is not None and ((sheet_start is not None and sta < sheet_start-1e-3) or
                                    (sheet_end is not None and sta > sheet_end+1e-3)):
                counts['curve_text_station_excluded']+=1
                counts['skipped']+=1
                continue
        leader = typ=='LINE' and layer.casefold() == '곡선인출선'.casefold()
        if leader and fl_points is not None:
            # Use the endpoint nearest to FL; v9 leader direction is not guaranteed.
            sta0,offset0=_station_of_point(e.dxf.start,fl_points,fl_distances,station_origin)
            sta1,offset1=_station_of_point(e.dxf.end,fl_points,fl_distances,station_origin)
            sta,offset=(sta0,offset0) if offset0 <= offset1 else (sta1,offset1)
            if (sta is None or offset > 2.0 or
                (sheet_start is not None and sta < sheet_start-1e-5) or
                (sheet_end is not None and sta > sheet_end+1e-5)):
                counts['curve_leader_station_excluded']+=1
                counts['skipped']+=1
                continue
        if typ=='LINE':
            # Tick lines are centered on FL; sheet membership must be checked
            # BEFORE geometric clipping (otherwise later stations can leak in).
            if layer.casefold() == '보조측점'.casefold() and fl_points is not None:
                midpoint = ((e.dxf.start.x+e.dxf.end.x)/2,
                            (e.dxf.start.y+e.dxf.end.y)/2)
                sta, offset = station_cache[e.dxf.handle] if station_cache is not None else _station_of_point(midpoint, fl_points, fl_distances, station_origin)
                if (sta is None or offset > 2.0 or
                    (sheet_start is not None and sta < sheet_start-1e-5) or
                    (sheet_end is not None and sta > sheet_end+1e-5)):
                    counts['skipped'] += 1
                    continue
            a=transform(e.dxf.start);b=transform(e.dxf.end)
            if leader and matchlines is not None:
                original=(a,b)
                for (point,tangent),keep_positive in zip(matchlines,(True,False)):
                    if (a,b) is None: break
                    segment_match=_clip_halfplane(a,b,point,tangent,keep_positive)
                    if segment_match is None:
                        a=b=None
                        break
                    a,b=segment_match
                if a is None:
                    counts['curve_leader_station_excluded']+=1
                    counts['skipped']+=1
                    continue
                if math.dist(a,original[0])>1e-6 or math.dist(b,original[1])>1e-6:
                    counts['curve_leader_matchline_clipped']+=1
            segment=clip(a,b,PLAN_RECT)
            if segment and math.dist(*segment)>1e-8:
                dst.add_line(*segment,dxfattribs=attrs);counts['LINE']+=1
                if leader: counts['curve_leader_drawn']+=1
            else:counts['skipped']+=1
        elif typ=='CIRCLE':
            c=transform(e.dxf.center);r=e.dxf.radius*k
            if _inside(c,margin=r):
                dst.add_circle(c,r,dxfattribs=attrs);counts['CIRCLE']+=1
            else:counts['skipped']+=1
        elif typ=='TEXT':
            p=transform(e.dxf.insert)
            # Anchor-based filtering; text extents are not clipped in this version.
            if _inside(p,margin=1) or layer.casefold() == '곡선제원문자'.casefold():
                attrs.update(insert=p,height=e.dxf.get('height',2.5)*k,
                             rotation=(e.dxf.get('rotation',0)-math.degrees(angle_rad))%360)
                if e.dxf.hasattr('style') and e.dxf.style in target_doc.styles:attrs['style']=e.dxf.style
                if e.dxf.hasattr('width'):attrs['width']=e.dxf.width
                created=dst.add_text(e.dxf.text,dxfattribs=attrs)
                if layer.casefold() == '곡선제원문자'.casefold():
                    ext=bbox.extents([created],fast=True)
                    if (not ext.has_data or ext.extmin.x < PLAN_RECT[0]-1e-6 or
                        ext.extmin.y < PLAN_RECT[1]-1e-6 or
                        ext.extmax.x > PLAN_RECT[2]+1e-6 or
                        ext.extmax.y > PLAN_RECT[3]+1e-6):
                        dst.delete_entity(created);counts['skipped']+=1
                        counts['curve_text_frame_excluded']+=1
                        continue
                counts['TEXT']+=1
            else:counts['skipped']+=1
        elif typ=='MTEXT':
            p=transform(e.dxf.insert)
            if _inside(p,margin=1):
                attrs.update(insert=p,char_height=e.dxf.get('char_height',2.5)*k,
                             rotation=(e.dxf.get('rotation',0)-math.degrees(angle_rad))%360)
                dst.add_mtext(e.text,dxfattribs=attrs);counts['MTEXT']+=1
            else:counts['skipped']+=1
        else:counts['skipped']+=1
    return counts
