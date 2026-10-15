"""Symmetric parabolic railway vertical curves; stations in m, gradients in permille.

This independent calculation module does not change approved v12.2 drawings.
"""
from __future__ import annotations
from dataclasses import dataclass
from bisect import bisect_right
import math


@dataclass(frozen=True)
class VerticalCurve:
    vip_index: int
    vip_sta: float
    vip_elevation: float
    length: float
    pvc_sta: float
    pvt_sta: float
    pvc_elevation: float
    pvt_elevation: float
    in_grade: float  # permille
    out_grade: float  # permille

    @property
    def algebraic_difference(self) -> float:
        return self.out_grade - self.in_grade

    def evaluate(self, station: float) -> tuple[float, float]:
        if not self.pvc_sta - 1e-8 <= station <= self.pvt_sta + 1e-8:
            raise ValueError('종곡선 범위를 벗어난 측점입니다.')
        x = max(0., min(self.length, station - self.pvc_sta))
        g1 = self.in_grade / 1000
        delta = self.algebraic_difference / 1000
        z = self.pvc_elevation + g1*x + delta*x*x/(2*self.length)
        grade = self.in_grade + self.algebraic_difference*x/self.length
        return z, grade

    def extremum(self) -> tuple[float, float] | None:
        d = self.algebraic_difference
        if abs(d) < 1e-12:
            return None
        x = -self.in_grade * self.length / d
        if not 0 < x < self.length:
            return None
        sta = self.pvc_sta + x
        return sta, self.evaluate(sta)[0]


class VerticalAlignment:
    def __init__(self, vips: list[tuple[float, float]], lengths: dict[int, float] | None = None):
        """lengths: internal VIP index (0-based) -> full curve length in meters."""
        if len(vips) < 2:
            raise ValueError('VIP는 최소 2개 필요합니다.')
        self.vips = [(float(s), float(z)) for s,z in vips]
        if any(not (math.isfinite(s) and math.isfinite(z)) for s,z in self.vips):
            raise ValueError('VIP 측점/표고는 유한한 값이어야 합니다.')
        if any(b[0] <= a[0] for a,b in zip(self.vips,self.vips[1:])):
            raise ValueError('VIP 측점은 엄격하게 증가해야 합니다.')
        self.grades = [(b[1]-a[1])/(b[0]-a[0])*1000 for a,b in zip(self.vips,self.vips[1:])]
        self.curves: list[VerticalCurve] = []
        for idx, length in sorted((lengths or {}).items()):
            if not isinstance(idx,int) or not 0 < idx < len(self.vips)-1:
                raise ValueError(f'종곡선은 내부 VIP에만 지정할 수 있습니다: {idx}')
            length = float(length)
            if not math.isfinite(length) or length <= 0:
                raise ValueError(f'종곡선 길이는 양수여야 합니다: {idx}')
            sta, z = self.vips[idx]
            pvc, pvt = sta-length/2, sta+length/2
            if pvc < self.vips[idx-1][0] - 1e-9 or pvt > self.vips[idx+1][0] + 1e-9:
                raise ValueError(f'VIP {idx} 종곡선이 인접 VIP 범위를 초과합니다.')
            g1,g2 = self.grades[idx-1],self.grades[idx]
            self.curves.append(VerticalCurve(idx,sta,z,length,pvc,pvt,
                z-g1*length/2000,z+g2*length/2000,g1,g2))
        for a,b in zip(self.curves,self.curves[1:]):
            if a.pvt_sta > b.pvc_sta + 1e-9:
                raise ValueError(f'종곡선 중첩: VIP {a.vip_index}, {b.vip_index}')
        self._xs = [s for s,_ in self.vips]

    def evaluate(self, station: float) -> tuple[float, float]:
        """Return (design elevation m, instantaneous gradient permille)."""
        station = float(station)
        if not math.isfinite(station) or not self._xs[0] <= station <= self._xs[-1]:
            raise ValueError('설계 측점 범위를 벗어났습니다.')
        for curve in self.curves:
            if curve.pvc_sta <= station <= curve.pvt_sta:
                return curve.evaluate(station)
        idx = min(bisect_right(self._xs,station)-1,len(self.grades)-1)
        s,z = self.vips[idx]
        return z+(station-s)*self.grades[idx]/1000, self.grades[idx]

    def sample(self, interval: float = 25.) -> list[tuple[float,float,float]]:
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError('측점 간격은 양수여야 합니다.')
        start,end = self._xs[0],self._xs[-1]
        stations = {start,end,*self._xs}
        for curve in self.curves:
            stations.update((curve.pvc_sta,curve.pvt_sta))
            extreme = curve.extremum()
            if extreme:
                stations.add(extreme[0])
        n0 = math.ceil(start/interval)
        for n in range(n0,math.floor(end/interval)+1):
            stations.add(n*interval)
        return [(s,*self.evaluate(s)) for s in sorted(stations)]


def from_profile_dxf(dxf_path, lengths: dict[int, float], scale=None) -> VerticalAlignment:
    """Read v12.2 PLAN_PROFILE VIPs; keep original source DXF read-only."""
    from dxf_reader import extract_profile
    vips = extract_profile(dxf_path, scale=scale)
    return VerticalAlignment([(p.sta, p.elevation) for p in vips], lengths)
