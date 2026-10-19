"""v12.5.5-D.1.4: portal intersections in unscaled station/elevation coordinates."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class PortalSettings:
    sl_height: float = 1.0
    portal_length: float = 20.0  # SL_LENGTH; retain existing GUI/CSV compatibility
    slope: float = 1.5  # horizontal : vertical = slope : 1
    color: int = 6

    def validate(self):
        if not all(math.isfinite(v) and v > 0 for v in (self.sl_height, self.portal_length, self.slope)):
            raise ValueError('갱문 높이, 길이, 경사비는 모두 0보다 큰 유한한 숫자여야 합니다.')
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
    intersects the horizontal tangent roof extension from the junction.
    """
    settings.validate()
    if direction not in (-1, 1):
        raise ValueError('갱문 방향은 -1 또는 +1이어야 합니다.')
    tip = junction + direction * settings.portal_length
    base_j = elevation_at(junction) + outer_bottom
    base_t = elevation_at(tip) + outer_bottom
    wall_top = base_t + settings.sl_height
    roof_j = elevation_at(junction) + outer_top
    rise = roof_j - wall_top
    if rise <= 1e-9:
        raise ValueError('갱문 수직벽 상단이 터널 외측 상단보다 높습니다. SL_HEIGHT를 줄이세요.')
    # SLOPE is the REAL horizontal:vertical ratio, independent of print scales.
    # Calculate intersection in unscaled station/elevation space.
    run = rise * settings.slope
    # The intersection is computed on an unbounded roof extension, as in CAD.
    # With a tall tunnel and a short SL_LENGTH it can fall inside the tunnel;
    # retain the true intersection for inspection rather than inventing a point.
    intersection = tip - direction * run
    # Geometric feasibility in REAL station/elevation coordinates.
    # P must be between the portal tip and the tunnel junction, inclusive.
    # Never alter the true intersection to make an invalid input appear valid.
    outward_distance = (intersection - junction) * direction
    tolerance = 1e-8 * max(1.0, settings.portal_length)
    if outward_distance < -tolerance or outward_distance > settings.portal_length + tolerance:
        required_length = run
        raise ValueError(
            f'갱문 길이 부족 또는 교점 범위 이탈 (STA {junction:.2f}, '
            f'{"시점" if direction == -1 else "종점"}): '
            f'SL_LENGTH={settings.portal_length:.3f}m, '
            f'필요 최소 길이≈{required_length:.3f}m. '
            'SL_LENGTH, SL_HEIGHT 또는 SLOPE를 조정하세요.'
        )
    n = max(1, math.ceil(settings.portal_length / 2.0))
    base = [(junction + direction * settings.portal_length * i / n,
             elevation_at(junction + direction * settings.portal_length * i / n) + outer_bottom)
            for i in range(n + 1)]
    # Junction bottom -> tip bottom -> tip wall top -> slope/roof intersection
    # -> junction roof. Reversed orientation is valid for end portals.
    return base + [(tip, wall_top), (intersection, roof_j), (junction, roof_j)]


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
