"""Import a prepared bridge cross-section DXF as horizontal offset intervals.

Contract: X is transverse coordinate (metres); Y is elevation; 1 CAD unit = 1 m.
BRIDGE_CENTER: exactly one vertical LINE (X = bridge alignment center).
BRIDGE_SLAB: exactly one closed LWPOLYLINE outlining the slab.
BRIDGE_GIRDER: one closed LWPOLYLINE per girder, each with distinct X extents.
Only modelspace entities on these layers are inspected. All other layers ignored.
"""
from pathlib import Path
import math
import ezdxf
from bridge_plan import BridgePlanSection


def _outline(ent, layer):
    if ent.dxftype() != 'LWPOLYLINE':
        raise ValueError(f'{layer}: 닫힌 LWPOLYLINE만 허용합니다 ({ent.dxftype()} 발견).')
    if not ent.closed:
        raise ValueError(f'{layer}: 모든 단면 외곽선은 폐합 LWPOLYLINE이어야 합니다.')
    vertices = list(ent.get_points('xyb'))
    if len(vertices) < 3 or any(abs(b)>1e-10 for _,_,b in vertices):
        raise ValueError(f'{layer}: 최소 3개 절점이 필요하며 bulge 호는 지원하지 않습니다.')
    coords = [x for x,_,_ in vertices]
    if not all(math.isfinite(v) for v in coords) or max(coords)-min(coords)<1e-6:
        raise ValueError(f'{layer}: 유효한 가로 폭이 필요합니다.')
    return min(coords), max(coords)


def load_bridge_section(path):
    path = Path(path).expanduser().resolve()
    doc = ezdxf.readfile(path)
    entities = {'BRIDGE_CENTER': [], 'BRIDGE_SLAB': [], 'BRIDGE_GIRDER': []}
    for ent in doc.modelspace():
        layer = ent.dxf.layer.upper()
        if layer in entities:
            entities[layer].append(ent)
    centers=entities['BRIDGE_CENTER']
    if len(centers)!=1 or centers[0].dxftype()!='LINE':
        raise ValueError('BRIDGE_CENTER 레이어에 수직 LINE 1개가 필요합니다.')
    a,b=centers[0].dxf.start,centers[0].dxf.end
    if abs(a.x-b.x)>1e-7 or abs(a.y-b.y)<1e-7 or not all(math.isfinite(v) for v in (a.x,a.y,b.y)):
        raise ValueError('BRIDGE_CENTER는 단면 Y방향 수직 LINE이어야 합니다.')
    center=a.x
    slabs=entities['BRIDGE_SLAB']
    if len(slabs)!=1:
        raise ValueError('BRIDGE_SLAB 레이어에는 폐합 외곽선 1개가 필요합니다.')
    slab=_outline(slabs[0], 'BRIDGE_SLAB')
    girders=sorted((_outline(e,'BRIDGE_GIRDER') for e in entities['BRIDGE_GIRDER']),key=lambda p:p[0])
    if not girders:
        raise ValueError('BRIDGE_GIRDER 레이어에 거더 외곽선이 없습니다.')
    section=BridgePlanSection(slab[0]-center,slab[1]-center,tuple((l-center,r-center) for l,r in girders))
    section.validate()
    for previous,current in zip(girders,girders[1:]):
        if previous[1] > current[0]+1e-7:
            raise ValueError('거더의 횡방향 외곽이 서로 겹칩니다. 단면 레이어를 확인하세요.')
    return section
