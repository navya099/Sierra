"""Plan-first datum planner. A plot window is defined in paper coordinates.
Ground is deliberately excluded from datum planning and must be clipped by renderer.
"""
from dataclasses import dataclass
from bisect import bisect_right
import math

@dataclass(frozen=True)
class DatumConfig:
    horizontal_scale: float = 1000.
    vertical_scale: float = 400.
    plot_lower_y: float = 150.
    plot_upper_y: float = 250.
    datum_step_m: float = 10.
    safety_margin_m: float = 0.
    def __post_init__(self):
        if self.vertical_scale <= 0 or self.horizontal_scale <= 0 or self.datum_step_m <= 0:
            raise ValueError('축척과 기준 표고 간격은 양수여야 합니다.')
        if self.plot_upper_y <= self.plot_lower_y:
            raise ValueError('그래프 상한은 하한보다 커야 합니다.')
        if self.safety_margin_m < 0 or self.safety_margin_m * 2 >= self.elevation_window_m:
            raise ValueError('표고 안전 여유가 그래프 표시 범위보다 큽니다.')
    @property
    def elevation_window_m(self):
        return (self.plot_upper_y-self.plot_lower_y)*self.vertical_scale/1000
    @property
    def plot_height_mm(self):
        return self.plot_upper_y-self.plot_lower_y

@dataclass(frozen=True)
class DatumSegment:
    start_sta: float
    end_sta: float
    datum_el: float

def plan_datum_segments(ground_points, plan_points, config=None):
    """Center PLAN_PROFILE in the window. Split only if plan leaves it.

    Both profile arrays are accepted for API compatibility. Ground is ignored.
    Datum is the elevation at plot_lower_y, not the band's datum.
    """
    c=config or DatumConfig()
    p=sorted((float(x),float(y)) for x,y in plan_points)
    g=sorted((float(x),float(y)) for x,y in ground_points)
    if len(p)<2 or len(g)<2 or any(b[0]<=a[0] for a,b in zip(p,p[1:])):
        raise ValueError('유효한 계획선/지반선 데이터가 필요합니다.')
    start=max(p[0][0],g[0][0]); end=min(p[-1][0],g[-1][0])
    if start>=end: raise ValueError('공통 측점 범위가 없습니다.')
    xs=[x for x,_ in p]
    def at(x):
        i=max(0,min(bisect_right(xs,x)-1,len(p)-2))
        x0,y0=p[i];x1,y1=p[i+1]
        return y0+(y1-y0)*(x-x0)/(x1-x0)
    points=[(start,at(start))]+[(x,y) for x,y in p if start<x<end]+[(end,at(end))]
    window=c.elevation_window_m; margin=c.safety_margin_m; step=c.datum_step_m
    def centered_datum(el):
        # Choose nearest engineering step to the centered ideal, provided it fits.
        ideal=el-window/2
        lo=math.ceil((el-window+margin-1e-9)/step)
        hi=math.floor((el-margin+1e-9)/step)
        if lo>hi:
            raise ValueError('기준 표고 단위가 현재 표시 창에 비해 너무 큽니다.')
        k=math.floor(ideal/step+0.5)
        return min(max(k,lo),hi)*step
    segments=[]
    datum=centered_datum(points[0][1]); seg_start=start
    for (x0,y0),(x1,y1) in zip(points,points[1:]):
        x=x0; y=y0
        for _ in range(10000):
            low=datum+margin; high=datum+window-margin
            if low-1e-7<=y1<=high+1e-7: break
            if y1>high and y1>y:
                fraction=(high-y)/(y1-y)
            elif y1<low and y1<y:
                fraction=(low-y)/(y1-y)
            else:
                raise ValueError('기준 표고 분할 방향 판정 실패')
            cut=x+(x1-x)*max(0,min(1,fraction))
            el=y+(y1-y)*(cut-x)/(x1-x)
            new=centered_datum(el)
            if new==datum:
                # Exact-boundary numerical case: pick a feasible next datum.
                direction=1 if y1>high else -1
                new=datum+direction*step
                if not new+margin-1e-7<=el<=new+window-margin+1e-7:
                    raise ValueError('기준 표고 변경 불가: 안전 여유 또는 기준 간격 조정 필요')
            if cut>seg_start+1e-8:
                segments.append(DatumSegment(seg_start,cut,datum))
                seg_start=cut
            datum=new; x=cut; y=el
        else:
            raise ValueError('기준 표고 분할 횟수 초과')
    if end>seg_start+1e-8:
        segments.append(DatumSegment(seg_start,end,datum))
    return segments
