"""v12.5.5-D.1.4: portal intersections in unscaled station/elevation coordinates."""
from dataclasses import dataclass
import math
from pathlib import Path

@dataclass(frozen=True)
class PortalSettings:
    sl_height: float = 1.0
    portal_length: float = 20.0  # SL_LENGTH; retain existing GUI/CSV compatibility
    slope: float = 1.5  # horizontal : vertical = slope : 1
    color: int = 6
    custom_dxf: str = ""
    sl_width: float = 6.0
    plan_custom_dxf: str = ""

    def validate(self):
        if not all(math.isfinite(v) and v > 0 for v in (self.sl_height, self.portal_length, self.slope)):
            raise ValueError('갱문 높이, 길이, 경사비는 모두 0보다 큰 유한한 숫자여야 합니다.')
        if not math.isfinite(self.sl_width) or self.sl_width <= 0:
            raise ValueError('SL_WIDTH는 양수여야 합니다.')
        if self.custom_dxf and not Path(self.custom_dxf).is_file():
            raise ValueError(f'사용자 갱문 DXF 파일을 찾을 수 없습니다: {self.custom_dxf}')
        if self.plan_custom_dxf and not Path(self.plan_custom_dxf).is_file():
            raise ValueError(f'사용자 평면 갱문 DXF 파일을 찾을 수 없습니다: {self.plan_custom_dxf}')
        if type(self.color) is not int or not 1 <= self.color <= 255:
            raise ValueError('갱문 색상은 1~255 정수여야 합니다.')


def _clip_x(vertices, x_min, x_max):
    """Clip an ordered polygon in (station, elevation) to a station interval."""
    def clip(points, boundary, keep_greater):
        out = []
        for a, b in zip(points[-1:] + points[:-1], points):
            inside_a = a[0] >= boundary - 1e-9 if keep_greater else a[0] <= boundary + 1e-9
            inside_b = b[0] >= boundary - 1e-9 if keep_greater else b[0] <= boundary + 1e-9
            if inside_a != inside_b:
                t = (boundary - a[0]) / (b[0] - a[0])
                out.append((boundary, a[1] + t * (b[1] - a[1])))
            if inside_b:
                out.append(b)
        return out
    if not vertices:
        return []
    return clip(clip(vertices, x_min, True), x_max, False)


def portal_vertices(junction, direction, settings, elevation_at, outer_top, outer_bottom,
                    horizontal_scale=1000.0, vertical_scale=1000.0):
    """Return closed-outline vertices in world station/elevation coordinates.

    At the tunnel junction the base/roof use actual outer-bottom/outer-top.
    The portal tip is SL_LENGTH outward. A vertical SL_HEIGHT wall rises
    from the base at the tip. Its sloped roof rises toward the tunnel and
    intersects the actual outer roof profile, including grade and vertical curves.
    """
    settings.validate()
    if direction not in (-1, 1):
        raise ValueError('갱문 방향은 -1 또는 +1이어야 합니다.')
    tip = junction + direction * settings.portal_length
    base_j = elevation_at(junction) + outer_bottom
    base_t = elevation_at(tip) + outer_bottom
    wall_top = base_t + settings.sl_height
    roof_j = elevation_at(junction) + outer_top

    # Solve in REAL STA/EL coordinates; print scales must never affect P.
    # t=0 is the outer portal tip, t=L is the tunnel junction.
    # The rising portal slope intersects the actual (possibly curved)
    # outer roof elevation profile.
    def roof_at(t):
        sta = tip - direction * t
        return elevation_at(sta) + outer_top

    def residual(t):
        return wall_top + t / settings.slope - roof_at(t)

    n_scan = max(32, math.ceil(settings.portal_length / 0.25))
    t_prev, f_prev = 0.0, residual(0.0)
    intersection_run = None
    if abs(f_prev) < 1e-9:
        intersection_run = 0.0
    else:
        for i in range(1, n_scan + 1):
            t = settings.portal_length * i / n_scan
            f = residual(t)
            if abs(f) < 1e-9:
                intersection_run = t
                break
            if f_prev * f < 0:
                lo, hi = t_prev, t
                flo = f_prev
                for _ in range(65):
                    mid = (lo + hi) / 2
                    fm = residual(mid)
                    if abs(fm) < 1e-11 or hi - lo < 1e-10:
                        lo = hi = mid
                        break
                    if flo * fm <= 0:
                        hi = mid
                    else:
                        lo, flo = mid, fm
                intersection_run = (lo + hi) / 2
                break
            t_prev, f_prev = t, f

    if intersection_run is None:
        # The old horizontal-roof estimate is only a diagnostic hint;
        # it is NOT used as an intersection or a geometry substitute.
        approximate = max(0.0, (roof_j - wall_top) * settings.slope)
        raise ValueError(
            f'갱문 길이 부족 또는 교점 범위 이탈 (STA {junction:.2f}, '
            f'{"시점" if direction == -1 else "종점"}): '
            f'SL_LENGTH={settings.portal_length:.3f}m, '
            f'수평 천장 가정 시 필요 길이≈{approximate:.3f}m. '
            '실제 종단구배·종곡선을 반영한 갱문 경사선과 천장선의 교점이 '
            '갱문 범위 안에 없습니다. SL_LENGTH, SL_HEIGHT 또는 SLOPE를 조정하세요.'
        )

    intersection = tip - direction * intersection_run
    intersection_el = roof_at(intersection_run)
    n = max(1, math.ceil(settings.portal_length / 2.0))
    base = [(junction + direction * settings.portal_length * i / n,
             elevation_at(junction + direction * settings.portal_length * i / n) + outer_bottom)
            for i in range(n + 1)]

    # Follow the identical outer-roof elevation function from P to the
    # junction, including vertical curves; no horizontal shortcut.
    roof_length = settings.portal_length - intersection_run
    n_roof = max(1, math.ceil(roof_length / 2.0))
    roof = []
    for i in range(n_roof + 1):
        t = intersection_run + roof_length * i / n_roof
        sta = tip - direction * t
        roof.append((sta, roof_at(t)))
    roof[0] = (intersection, intersection_el)
    roof[-1] = (junction, roof_j)
    return base + [(tip, wall_top)] + roof


def draw_profile_portals(msp, structures, settings, start, end, datum_segments,
                         elevation_at, display_sta, display_el, outer_top, outer_bottom=-2.0,
                         horizontal_scale=1000.0, vertical_scale=1000.0):
    """Draw portal outlines, clipped independently to sheet and datum spans."""
    settings.validate()
    count = 0
    for seg in structures:
        if seg.kind != 'TUNNEL':
            continue
        for junction, direction in ((seg.start_sta, -1), (seg.end_sta, +1)):
            vertices = portal_vertices(junction, direction, settings, elevation_at,
                                       outer_top, outer_bottom, horizontal_scale, vertical_scale)
            for datum in datum_segments:
                a = max(start, datum.start_sta)
                b = min(end, datum.end_sta)
                if b <= a:
                    continue
                polygon = _clip_x(vertices, a, b)
                if len(polygon) < 3:
                    continue
                # Suppress degenerate polygons that touch only a boundary.
                if max(p[0] for p in polygon) - min(p[0] for p in polygon) < 1e-8:
                    continue
                points = [(display_sta(s), display_el(z, datum.datum_el)) for s, z in polygon]
                msp.add_lwpolyline(points, close=True, dxfattribs={'layer': 'TUNNEL_PORTAL'})
                count += 1
    return count
