"""Read prepared tunnel cross-section outlines in millimetres.

Modelspace layers: TUNNEL_OUTER and TUNNEL_INNER, each one closed
LWPOLYLINE. DXF (0, 0) is the design-grade reference point; Y is vertical.
The longitudinal representation uses vertical extrema only, not full arches.
"""
from dataclasses import dataclass
from pathlib import Path
import math
import ezdxf


@dataclass(frozen=True)
class TunnelSection:
    outer_bottom: float
    outer_top: float
    inner_bottom: float
    inner_top: float
    outer_left: float = -5.0
    outer_right: float = 5.0
    inner_left: float = -4.8
    inner_right: float = 4.8

    @property
    def body_height(self):
        return self.outer_top - self.outer_bottom

    @property
    def bottom_offset(self):
        return -self.outer_bottom

    def validate(self):
        a,b,c,d=self.outer_bottom,self.outer_top,self.inner_bottom,self.inner_top
        if not all(math.isfinite(x) for x in (a,b,c,d)) or not (a < c < d < b):
            raise ValueError('터널 내공의 상·하단이 라이닝 외곽 내부에 있어야 합니다.')
        if not (self.outer_left < self.inner_left < self.inner_right < self.outer_right):
            raise ValueError('터널 내공 좌우 폭은 외곽 내부에 있어야 합니다.')
        if a > 0:
            raise ValueError('터널 외측 하단은 계획선 기준점(0,0) 이하에 있어야 합니다.')


def _bounds(ent, layer):
    if ent.dxftype() != 'LWPOLYLINE' or not ent.closed:
        raise ValueError(f'{layer}: 폐합 LWPOLYLINE 1개가 필요합니다.')
    points=list(ent.get_points('xyb'))
    if len(points)<3:
        raise ValueError(f'{layer}: 최소 3개의 꼭짓점이 필요합니다.')
    # ezdxf bbox includes the true extrema of bulge arcs, unlike vertex-only bounds.
    from ezdxf import bbox
    bounds=bbox.extents([ent])
    if not bounds.has_data:
        raise ValueError(f'{layer}: 단면 외곽 범위를 읽을 수 없습니다.')
    vals=(bounds.extmin.x,bounds.extmin.y,bounds.extmax.x,bounds.extmax.y)
    if not all(math.isfinite(v) for v in vals) or vals[2]-vals[0]<=0 or vals[3]-vals[1]<=0:
        raise ValueError(f'{layer}: 유효한 외곽 범위가 필요합니다.')
    return vals


def load_tunnel_section(path, unit_scale=0.001):
    path=Path(path).expanduser().resolve()
    if not math.isfinite(unit_scale) or unit_scale<=0:
        raise ValueError('단위 변환 계수가 올바르지 않습니다.')
    doc=ezdxf.readfile(path)
    found={'TUNNEL_OUTER':[],'TUNNEL_INNER':[]}
    for ent in doc.modelspace():
        layer=ent.dxf.layer.upper()
        if layer in found:
            found[layer].append(ent)
    for layer,items in found.items():
        if len(items)!=1:
            raise ValueError(f'{layer} 레이어에 폐합 LWPOLYLINE 1개가 필요합니다. (현재 {len(items)}개)')
    outer=_bounds(found['TUNNEL_OUTER'][0],'TUNNEL_OUTER')
    inner=_bounds(found['TUNNEL_INNER'][0],'TUNNEL_INNER')
    if not (outer[0] < inner[0] < inner[2] < outer[2]):
        raise ValueError('내공의 좌우 외곽도 라이닝 외측 내부에 있어야 합니다.')
    section=TunnelSection(outer[1]*unit_scale,outer[3]*unit_scale,inner[1]*unit_scale,inner[3]*unit_scale,outer[0]*unit_scale,outer[2]*unit_scale,inner[0]*unit_scale,inner[2]*unit_scale)
    section.validate()
    return section
