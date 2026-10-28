"""v1.7: copy station/curve annotations from source PLAN DXF into sheet-local PLAN area.
Does not mutate source entities. Coordinates are DXF XY (already civil XY swapped by producer).
"""
import math
from .combined_plan_profile_v1_6_core import PLAN_RECT, clip

DEFAULT_LAYERS = ('km심볼','200심볼','km문자','200문자','보조측점','곡선인출선','곡선제원문자','IP교점선','IP문자')

def _inside(p, rect=PLAN_RECT, margin=0):
    return rect[0]+margin <= p[0] <= rect[2]-margin and rect[1]+margin <= p[1] <= rect[3]-margin

def render_plan_entities(source_doc, target_doc, transform, angle_rad, horizontal_scale, layers=DEFAULT_LAYERS):
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
        if typ=='LINE':
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
