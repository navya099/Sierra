"""Railway profile station/elevation calculator (DXF read-only).

Ground: GROUND_PROFILE LWPOLYLINE (or legacy 2D POLYLINE).
Design: PLAN_PROFILE LWPOLYLINE via dxf_reader.extract_profile().
CAD X = station [m], CAD Y = elevation [m], both 1:1.
"""
from __future__ import annotations

import argparse
import csv
import math
from bisect import bisect_right
from dataclasses import asdict, dataclass
from pathlib import Path

import ezdxf
from dxf_reader import extract_profile
from profile_scale import ProfileScale


@dataclass(frozen=True)
class StationResult:
    sta: float
    ground_el: float
    plan_el: float
    difference: float  # plan - ground
    gradient_permille: float
    classification: str


def read_ground_points(dxf_path: str | Path, layer: str = "GROUND_PROFILE", scale: ProfileScale | None = None) -> list[tuple[float, float]]:
    doc = ezdxf.readfile(str(dxf_path))
    matches = [e for e in doc.modelspace() if e.dxftype() in ("LWPOLYLINE", "POLYLINE")
               and e.dxf.layer.casefold() == layer.casefold()]
    if len(matches) != 1:
        raise ValueError(f"'{layer}' 레이어의 지반고 폴리라인이 1개 필요합니다 (현재 {len(matches)}개).")
    e = matches[0]
    if e.is_closed:
        raise ValueError("지반고 폴리라인은 열린 선이어야 합니다.")
    if e.dxftype() == "LWPOLYLINE":
        if any(abs(b) > 1e-12 for _, _, b in e.get_points("xyb")):
            raise ValueError("지반고의 호(bulge)는 지원하지 않습니다.")
        if abs(e.dxf.get("elevation", 0)) > 1e-9:
            raise ValueError("지반고 LWPOLYLINE elevation은 0이어야 합니다.")
        extrusion = e.dxf.get("extrusion", (0, 0, 1))
        if any(abs(float(a)-b)>1e-9 for a,b in zip(extrusion, (0,0,1))):
            raise ValueError("지반고 비표준 extrusion은 지원하지 않습니다.")
        points = [(float(x), float(y)) for x, y in e.get_points("xy")]
    else:
        if not e.is_2d_polyline:
            raise ValueError("지반고 POLYLINE은 2D 형식이어야 합니다.")
        if any(abs(v.dxf.get("bulge", 0)) > 1e-12 for v in e.vertices):
            raise ValueError("지반고의 호(bulge)는 지원하지 않습니다.")
        points = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
    points = (scale or ProfileScale()).convert_points_to_real(points)
    validate_points(points, "지반고")
    return points


def validate_points(points: list[tuple[float, float]], name: str) -> None:
    if len(points) < 2:
        raise ValueError(f"{name} 정점이 최소 2개 필요합니다.")
    for x, y in points:
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"{name} 좌표에 NaN/무한대가 있습니다.")
    for a, b in zip(points, points[1:]):
        if b[0] <= a[0]:
            raise ValueError(f"{name} 측점은 엄격하게 증가해야 합니다: {a[0]} → {b[0]}")


class PiecewiseLinear:
    def __init__(self, points: list[tuple[float, float]]):
        validate_points(points, "보간 입력")
        self.points = points
        self.xs = [p[0] for p in points]

    def at(self, sta: float) -> tuple[float, float]:
        if sta < self.xs[0] - 1e-8 or sta > self.xs[-1] + 1e-8:
            raise ValueError(f"측점 {sta}는 데이터 범위 밖입니다: {self.xs[0]}~{self.xs[-1]}")
        idx = max(0, min(bisect_right(self.xs, sta) - 1, len(self.xs) - 2))
        x0, y0 = self.points[idx]
        x1, y1 = self.points[idx + 1]
        t = (sta - x0) / (x1 - x0)
        return y0 + t * (y1 - y0), (y1 - y0) / (x1 - x0) * 1000


def calculate_stations(
    dxf_path: str | Path,
    interval: float = 25.0,
    ground_layer: str = "GROUND_PROFILE",
    plan_layer: str = "PLAN_PROFILE",
    include_vips: bool = True,
    scale: ProfileScale | None = None,
) -> list[StationResult]:
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("증분측점 간격은 양수인 유한한 값이어야 합니다.")
    ground = PiecewiseLinear(read_ground_points(dxf_path, ground_layer, scale))
    vip = extract_profile(dxf_path, layer=plan_layer, scale=scale)
    plan = PiecewiseLinear([(p.sta, p.elevation) for p in vip])
    start = max(ground.xs[0], plan.xs[0])
    end = min(ground.xs[-1], plan.xs[-1])
    if end <= start:
        raise ValueError("지반고와 계획 종단의 공통 측점 구간이 없습니다.")

    # Absolute station multiples (e.g., 0,25,50...), plus shared endpoints.
    first_index = math.ceil((start - 1e-9) / interval)
    count = max(0, math.floor((end + 1e-9) / interval) - first_index + 1)
    stations = [start, end]
    stations.extend((first_index + i) * interval for i in range(count))
    if include_vips:
        stations.extend(p.sta for p in vip if start <= p.sta <= end)
    stations.sort()
    unique = []
    for s in stations:
        s = min(end, max(start, s))
        if not unique or abs(s - unique[-1]) > 1e-7:
            unique.append(s)

    rows = []
    for sta in unique:
        ground_el, _ = ground.at(sta)
        plan_el, gradient = plan.at(sta)
        diff = plan_el - ground_el
        kind = "성토" if diff > 1e-6 else "절토" if diff < -1e-6 else "일치"
        rows.append(StationResult(sta, ground_el, plan_el, diff, gradient, kind))
    return rows


def export_csv(rows: list[StationResult], output_path: str | Path) -> None:
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(StationResult.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(r) for r in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="DXF 지반고/계획고 증분측점 계산")
    parser.add_argument("dxf", help="설계용 converted_dxf.dxf")
    parser.add_argument("--interval", type=float, default=25.0, help="증분측점 간격(m), 기본 25")
    parser.add_argument("--csv", help="결과 CSV 경로")
    parser.add_argument("--ground-layer", default="GROUND_PROFILE")
    parser.add_argument("--plan-layer", default="PLAN_PROFILE")
    parser.add_argument("--no-vips", action="store_true", help="VIP 측점 추가 출력 안 함")
    parser.add_argument("--h", type=float, default=1)
    parser.add_argument("--v", type=float, default=1)
    parser.add_argument("--datum", type=float, default=0)
    parser.add_argument("--station-origin", type=float, default=0)
    parser.add_argument("--paper-mm", action="store_true")
    args = parser.parse_args()
    scale = ProfileScale(args.h, args.v, args.datum, args.station_origin, "paper_mm" if args.paper_mm else "legacy")
    rows = calculate_stations(args.dxf, args.interval, args.ground_layer, args.plan_layer, not args.no_vips, scale=scale)
    print(f"{'STA':>10} {'지반고':>12} {'계획고':>12} {'표고차':>12} {'구배(‰)':>12} {'구분':>6}")
    for r in rows:
        print(f"{r.sta:10.3f} {r.ground_el:12.3f} {r.plan_el:12.3f} {r.difference:+12.3f} {r.gradient_permille:+12.3f} {r.classification:>6}")
    output = Path(args.csv) if args.csv else Path(args.dxf).with_name("profile_station_result.csv")
    export_csv(rows, output)
    print(f"CSV 저장 완료: {output}")


if __name__ == "__main__":
    main()
