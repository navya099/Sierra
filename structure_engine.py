"""v12.5.0: preliminary bridge/tunnel candidate engine (real station/elevation metres).

Candidates are continuous cut/fill spans, qualified by *maximum* depth and total span
length. This is a screening heuristic, not a final civil engineering design rule.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from bisect import bisect_right
from pathlib import Path
import argparse
import csv
import json
import math

from profile_calculator import PiecewiseLinear, read_ground_points
from vertical_curve import VerticalAlignment, from_profile_dxf


@dataclass(frozen=True)
class StructureSettings:
    tunnel_cut_threshold: float = 40.0
    tunnel_min_length: float = 100.0
    bridge_fill_threshold: float = 15.0
    bridge_min_length: float = 100.0
    bridge_start_fill_h: float = 5.0
    girder_clearance_depth: float = 0.0  # top offset + girder height

    def __post_init__(self):
        if any(not math.isfinite(v) or v < 0 for v in asdict(self).values()):
            raise ValueError("구조물 판정 기준은 0 이상의 유한한 값이어야 합니다.")


@dataclass(frozen=True)
class StructureSegment:
    kind: str  # TUNNEL / BRIDGE
    start_sta: float
    end_sta: float
    max_height: float
    peak_sta: float
    source: str = "AUTO"
    name: str = ""

    @property
    def length(self):
        return self.end_sta - self.start_sta


def _roots(fn, a, b, tol=1e-8):
    fa, fb = fn(a), fn(b)
    if abs(fa) <= tol:
        return a
    if abs(fb) <= tol:
        return b
    if fa * fb > 0:
        return None
    for _ in range(65):
        mid = (a + b) / 2
        fm = fn(mid)
        if abs(fm) < 1e-10 or b-a < 1e-8:
            return mid
        if fa * fm <= 0:
            b, fb = mid, fm
        else:
            a, fa = mid, fm
    return (a+b)/2


def detect_structures(ground_points, alignment: VerticalAlignment,
                      settings: StructureSettings = StructureSettings()):
    ground = PiecewiseLinear(list(ground_points))
    lo = max(ground.xs[0], alignment.vips[0][0])
    hi = min(ground.xs[-1], alignment.vips[-1][0])
    if hi <= lo:
        raise ValueError("지반선과 계획선의 공통 측점 구간이 없습니다.")
    # On each elementary interval, design-ground is quadratic (or linear).
    # Include curve turning points, which may contain two crossings even when
    # the endpoint differences have the same sign.
    knots = {lo, hi}
    knots.update(x for x in ground.xs if lo < x < hi)
    knots.update(x for x, _ in alignment.vips if lo < x < hi)
    for c in alignment.curves:
        knots.update(x for x in (c.pvc_sta, c.pvt_sta) if lo < x < hi)
    knots = sorted(knots)
    def diff(s):
        return alignment.evaluate(s)[0] - ground.at(s)[0]
    fine = set(knots)
    for a,b in zip(knots,knots[1:]):
        mid=(a+b)/2
        g_slope=ground.at(mid)[1]
        # Stationary point of plan-ground inside a curve.
        curve=next((c for c in alignment.curves if c.pvc_sta <= mid <= c.pvt_sta), None)
        if curve and abs(curve.algebraic_difference)>1e-12:
            x=(g_slope-curve.in_grade)*curve.length/curve.algebraic_difference
            s=curve.pvc_sta+x
            if a+1e-8 < s < b-1e-8:
                fine.add(s)
    fine=sorted(fine)
    roots=[]
    for a,b in zip(fine,fine[1:]):
        if diff(a)*diff(b) < 0:
            root=_roots(diff,a,b)
            if root is not None:
                roots.append(root)
    cuts=sorted(set(fine+roots))
    spans=[]
    active=None
    for a,b in zip(cuts,cuts[1:]):
        if b-a < 1e-7:
            continue
        val=diff((a+b)/2)
        kind='BRIDGE' if val>1e-8 else 'TUNNEL' if val < -1e-8 else None
        if kind is None:
            if active:
                spans.append(active)
                active=None
            continue
        if active and active[0]==kind and abs(active[2]-a)<1e-6:
            active=(kind,active[1],b)
        else:
            if active:
                spans.append(active)
            active=(kind,a,b)
    if active:
        spans.append(active)
    results=[]
    counters={'TUNNEL': 0, 'BRIDGE': 0}
    for kind,a,b in spans:
        length=b-a
        min_length=settings.tunnel_min_length if kind=='TUNNEL' else settings.bridge_min_length
        threshold=settings.tunnel_cut_threshold if kind=='TUNNEL' else settings.bridge_fill_threshold
        if length+1e-7 < min_length:
            continue
        candidates=[a,b]+[x for x in fine if a < x < b]
        peak=max(candidates,key=lambda x: abs(diff(x)))
        height=abs(diff(peak))
        if height+1e-7 >= threshold:
            if kind == 'BRIDGE':
                # Qualify using the original fill span, then trim to the region
                # where the full girder depth fits above the ground surface.
                boundary=max(settings.bridge_start_fill_h,settings.girder_clearance_depth)
                if boundary > 0:
                    intervals=[]
                    parts=[a]+[x for x in fine if a < x < b]+[b]
                    crossings=[]
                    for x,y in zip(parts,parts[1:]):
                        fx,fy=diff(x)-boundary,diff(y)-boundary
                        if fx*fy < 0:
                            r=_roots(lambda sta: diff(sta)-boundary,x,y)
                            if r is not None: crossings.append(r)
                    boundaries=sorted(set(parts+crossings))
                    active_start=None
                    for x,y in zip(boundaries,boundaries[1:]):
                        if y-x < 1e-7: continue
                        above=diff((x+y)/2) >= boundary-1e-8
                        if above and active_start is None: active_start=x
                        if not above and active_start is not None:
                            intervals.append((active_start,x)); active_start=None
                    if active_start is not None: intervals.append((active_start,b))
                    # Independent eligible regions; never bridge across a low-fill gap.
                    for start,end in intervals:
                        if end-start+1e-7 < min_length: continue
                        local=[start,end]+[x for x in fine if start < x < end]
                        local_peak=max(local,key=diff)
                        counters[kind]+=1
                        results.append(StructureSegment(kind,start,end,diff(local_peak),local_peak,'AUTO',f'B{counters[kind]}'))
                    continue
            counters[kind] += 1
            prefix = 'T' if kind == 'TUNNEL' else 'B'
            results.append(StructureSegment(kind,a,b,height,peak,'AUTO',f'{prefix}{counters[kind]}'))
    return results


def auto_from_dxf(dxf_path, curve_lengths=None, settings=StructureSettings()):
    ground=read_ground_points(dxf_path)
    alignment=from_profile_dxf(dxf_path,curve_lengths or {})
    return detect_structures(ground,alignment,settings)


def export_csv(segments, path):
    fields=['kind','name','start_sta','end_sta','length','max_height','peak_sta','source']
    with open(path,'w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for s in segments:
            d=asdict(s)
            d['length']=s.length
            writer.writerow(d)


def load_manual_csv(path):
    """Read editable final segment list. Manual changes remain separate from AUTO generation."""
    result=[]
    with open(path,encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            kind=row['kind'].strip().upper()
            if kind not in ('BRIDGE','TUNNEL'):
                raise ValueError(f"잘못된 구조물 유형: {kind}")
            a,b=float(row['start_sta']),float(row['end_sta'])
            if not all(map(math.isfinite,(a,b))) or b<=a:
                raise ValueError('구조물 시작/종료 측점 오류')
            result.append(StructureSegment(kind,a,b,float(row.get('max_height') or 0),
                float(row.get('peak_sta') or a),'MANUAL',row.get('name','')))
    return result


def main():
    ap=argparse.ArgumentParser(description='v12.5 구조물 자동 판정 (DXF 읽기 전용)')
    ap.add_argument('dxf')
    ap.add_argument('output_csv')
    ap.add_argument('--tunnel-cut',type=float,default=40)
    ap.add_argument('--tunnel-min',type=float,default=100)
    ap.add_argument('--bridge-fill',type=float,default=15)
    ap.add_argument('--bridge-min',type=float,default=100)
    ap.add_argument('--bridge-start-fill',type=float,default=5)
    ap.add_argument('--girder-depth',type=float,default=0,help='girder_top_offset + girder_h')
    ap.add_argument('--curves-json',help='VIP 인덱스(0부터 시작): 종곡선 길이 사전 JSON')
    args=ap.parse_args()
    lengths={int(k):float(v) for k,v in json.loads(Path(args.curves_json).read_text(encoding='utf-8')).items()} if args.curves_json else {}
    settings=StructureSettings(args.tunnel_cut,args.tunnel_min,args.bridge_fill,args.bridge_min,args.bridge_start_fill,args.girder_depth)
    segments=auto_from_dxf(args.dxf,lengths,settings)
    export_csv(segments,args.output_csv)
    print(f'구조물 후보 {len(segments)}개 저장: {args.output_csv}')
    for s in segments:
        print(f'{s.kind}: {s.start_sta:.3f} ~ {s.end_sta:.3f}m, L={s.length:.3f}m, MAX={s.max_height:.3f}m')

if __name__=='__main__':
    main()
