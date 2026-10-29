"""v1.7: copy station/curve annotations from source PLAN DXF into sheet-local PLAN area.
Does not mutate source entities. Coordinates are DXF XY (already civil XY swapped by producer).
"""
import math
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

def render_plan_entities(source_doc, target_doc, transform, angle_rad, horizontal_scale,
                         layers=DEFAULT_LAYERS, *, sheet_start=None, sheet_end=None,
                         fl_points=None, fl_distances=None, station_origin=0., station_cache=None):
    """Transform selected DXF modelspace entities; clip LINE, reject out-of-frame labels/symbols.
    Source entities in IP_Block_* are deliberately excluded: their absolute block coordinates
    and zero insertion require a separate safe block handler.
    """
    src=source_doc.modelspace(); dst=target_doc.modelspace()
    k=1000.0/horizontal_scale
    counts={'LINE':0,'TEXT':0,'MTEXT':0,'CIRCLE':0,'skipped':0}
    selected={name.casefold() for name in layers}
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
            segment=clip(a,b,PLAN_RECT)
            if segment and math.dist(*segment)>1e-8:
                dst.add_line(*segment,dxfattribs=attrs);counts['LINE']+=1
            else:counts['skipped']+=1
        elif typ=='CIRCLE':
            c=transform(e.dxf.center);r=e.dxf.radius*k
            if _inside(c,margin=r):
                dst.add_circle(c,r,dxfattribs=attrs);counts['CIRCLE']+=1
            else:counts['skipped']+=1
        elif typ=='TEXT':
            p=transform(e.dxf.insert)
            # Anchor-based filtering; text extents are not clipped in this version.
            if _inside(p,margin=1):
                attrs.update(insert=p,height=e.dxf.get('height',2.5)*k,
                             rotation=(e.dxf.get('rotation',0)-math.degrees(angle_rad))%360)
                if e.dxf.hasattr('style') and e.dxf.style in target_doc.styles:attrs['style']=e.dxf.style
                if e.dxf.hasattr('width'):attrs['width']=e.dxf.width
                dst.add_text(e.dxf.text,dxfattribs=attrs);counts['TEXT']+=1
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
