"""REG2-PERF1-A: read-only common FL geometry core.

No existing Sierra module imports this yet. This phase only establishes parity.
"""
from __future__ import annotations

from bisect import bisect_right
import math


def read_fl(doc):
    """Extract clean XY vertices and cumulative distances from an already-loaded DXF."""
    matches = [
        e for e in doc.modelspace().query("LWPOLYLINE")
        if e.dxf.layer.casefold() == "fl"
    ]
    if len(matches) != 1:
        raise ValueError(f"FL LWPOLYLINE must be exactly one (found {len(matches)})")
    ent = matches[0]
    if ent.closed or any(abs(b) > 1e-12 for _, _, b in ent.get_points("xyb")):
        raise ValueError("FL must be an open polyline without bulges")
    raw = [(float(x), float(y)) for x, y in ent.get_points("xy")]
    if len(raw) < 2:
        raise ValueError("FL must have at least two vertices")
    clean = [raw[0]]
    distances = [0.0]
    for point in raw[1:]:
        length = math.dist(clean[-1], point)
        if length < 1e-8:
            continue
        clean.append(point)
        distances.append(distances[-1] + length)
    if len(clean) < 2:
        raise ValueError("FL length is zero")
    return clean, distances


def position_and_tangent_at(sta, points, distances):
    """Return (XY, unit tangent), matching final_plan_vip.position_at semantics."""
    if sta < -1e-6 or sta > distances[-1] + 1e-6:
        raise ValueError(f"STA {sta:.3f} outside FL range 0..{distances[-1]:.3f}")
    sta = max(0.0, min(sta, distances[-1]))
    idx = min(bisect_right(distances, sta) - 1, len(points) - 2)
    a, b = points[idx], points[idx + 1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    segment = distances[idx + 1] - distances[idx]
    t = (sta - distances[idx]) / segment
    return (a[0] + dx*t, a[1] + dy*t), (dx/segment, dy/segment)


def position_at(sta, points, distances):
    """Return XY only, matching combined_plan_profile_v1_7_core.position_at."""
    return position_and_tangent_at(sta, points, distances)[0]
