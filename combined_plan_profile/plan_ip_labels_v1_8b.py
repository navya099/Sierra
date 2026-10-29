"""v1.8-B: Preserve original IP text/table geometry; no forced relocation.

The producer stores absolute text coordinates inside IP_Block_* and inserts
those blocks at (0,0). We flatten only those TEXT entities into sheet space.
Whole IP tables are rejected if any text falls outside the PLAN rectangle.
"""
import math
from ezdxf import bbox
from .combined_plan_profile_v1_6_core import PLAN_RECT


def _within(ext, rect=PLAN_RECT, eps=1e-6):
    return (ext.has_data and ext.extmin.x >= rect[0]-eps and
            ext.extmin.y >= rect[1]-eps and
            ext.extmax.x <= rect[2]+eps and
            ext.extmax.y <= rect[3]+eps)


def _add_text(dst, ent, transform, angle_rad, k, layer):
    p=transform(ent.dxf.insert)
    attrs={'layer':layer, 'insert':p,
           'height':ent.dxf.get('height',2.5)*k,
           'rotation':(ent.dxf.get('rotation',0)-math.degrees(angle_rad))%360}
    if ent.dxf.hasattr('color'): attrs['color']=ent.dxf.color
    if ent.dxf.hasattr('width'): attrs['width']=ent.dxf.width
    if ent.dxf.hasattr('style') and ent.dxf.style in dst.doc.styles:
        attrs['style']=ent.dxf.style
    return dst.add_text(ent.dxf.text,dxfattribs=attrs)


def render_ip_labels(source_doc,target_doc,transform,angle_rad,horizontal_scale):
    src=source_doc.modelspace(); dst=target_doc.modelspace()
    k=1000.0/horizontal_scale
    for name in ('IP문자','IP제원표'):
        if name not in target_doc.layers:
            original=source_doc.layers.get(name) if name in source_doc.layers else None
            target_doc.layers.new(name,dxfattribs={'color':original.dxf.get('color',7) if original else 7})
    counts={'ip_text_drawn':0,'ip_text_excluded':0,'ip_table_drawn':0,'ip_table_excluded':0}
    # IP number: reject if actual transformed text bounding box crosses frame.
    for ent in src:
        if ent.dxf.layer.casefold()!='ip문자' or ent.dxftype()!='TEXT':continue
        new=_add_text(dst,ent,transform,angle_rad,k,'IP문자')
        if _within(bbox.extents([new],fast=True)):
            counts['ip_text_drawn']+=1
        else:
            dst.delete_entity(new);counts['ip_text_excluded']+=1
    # Each original INSERT references a block whose TEXT coordinates are absolute.
    # Preserve its table as a group: never leave a partial IP data table.
    for ins in src:
        if ins.dxftype()!='INSERT' or not ins.dxf.name.startswith('IP_Block_'):
            continue
        block=source_doc.blocks.get(ins.dxf.name)
        if block is None:continue
        # Original producer's IP_Block_* are all unrotated, unit-scale at 0,0.
        # Fail explicitly for unexpected inserts rather than silently distort them.
        if (math.dist(ins.dxf.insert,(0,0,0))>1e-8 or
            abs(ins.dxf.get('rotation',0))>1e-8 or
            abs(ins.dxf.get('xscale',1)-1)>1e-8 or
            abs(ins.dxf.get('yscale',1)-1)>1e-8):
            raise ValueError(f'Unsupported IP block insertion: {ins.dxf.name}')
        entities=[e for e in block if e.dxftype()=='TEXT']
        if not entities:continue
        created=[_add_text(dst,e,transform,angle_rad,k,'IP제원표') for e in entities]
        if _within(bbox.extents(created,fast=True)):
            counts['ip_table_drawn']+=1
        else:
            for e in created:dst.delete_entity(e)
            counts['ip_table_excluded']+=1
    return counts
