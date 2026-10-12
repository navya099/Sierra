"""Read-only extraction of railway vertical alignment from a DXF LWPOLYLINE."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import argparse
import csv
import json
import math

import ezdxf
from profile_scale import ProfileScale


@dataclass(frozen=True)
class ProfilePoint:
    kind: str
    sta: float
    elevation: float
    gradient_in: float | None
    gradient_out: float | None
    delta_gradient: float | None

    def as_dict(self) -> dict:
        return asdict(self)


def _slope(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = b[0] - a[0]
    if dx <= 0:
        raise ValueError(f"측점은 엄격하게 증가해야 합니다: {a[0]} → {b[0]}")
    return (b[1] - a[1]) / dx * 1000.0


def extract_profile(
    path: str | Path,
    layer: str = "PLAN_PROFILE",
    gradient_tolerance: float = 1e-5,
    scale: ProfileScale | None = None,
) -> list[ProfilePoint]:
    """Return BP/VIP/EP from one open, straight-segment LWPOLYLINE.

    gradient_tolerance is in permille (‰).  Input coordinates are STA and EL
    in meters (1:1); the input DXF is never modified.
    """
    if gradient_tolerance < 0:
        raise ValueError("gradient_tolerance은 0 이상이어야 합니다.")
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"DXF 파일을 찾을 수 없습니다: {path}")

    doc = ezdxf.readfile(str(path))
    entities = [
        ent for ent in doc.modelspace().query("LWPOLYLINE")
        if ent.dxf.layer.casefold() == layer.casefold()
    ]
    if len(entities) != 1:
        raise ValueError(
            f"'{layer}' 레이어에 LWPOLYLINE이 정확히 1개 필요합니다. "
            f"현재 {len(entities)}개입니다."
        )

    entity = entities[0]
    if entity.closed:
        raise ValueError("계획 종단 LWPOLYLINE은 닫혀 있으면 안 됩니다.")
    if abs(entity.dxf.get("elevation", 0.0)) > 1e-9:
        raise ValueError("LWPOLYLINE elevation은 0이어야 합니다 (2D 종단 전용).")
    extrusion = entity.dxf.get("extrusion", (0, 0, 1))
    if any(abs(float(a) - b) > 1e-9 for a, b in zip(extrusion, (0, 0, 1))):
        raise ValueError("비표준 extrusion 방향은 지원하지 않습니다.")

    raw = list(entity.get_points("xyb"))
    if len(raw) < 2:
        raise ValueError("계획 종단 정점이 최소 2개 필요합니다.")
    if any(abs(bulge) > 1e-12 for _, _, bulge in raw):
        raise ValueError("호(bulge)가 포함된 LWPOLYLINE은 아직 지원하지 않습니다.")
    scale = scale or ProfileScale()
    points = [scale.to_real(x, y) for x, y, _ in raw]
    if not all(math.isfinite(v) for point in points for v in point):
        raise ValueError("좌표에 NaN 또는 무한대가 있습니다.")

    slopes = [_slope(points[i], points[i + 1]) for i in range(len(points) - 1)]
    keep = [0]
    for i in range(1, len(points) - 1):
        if abs(slopes[i] - slopes[i - 1]) > gradient_tolerance:
            keep.append(i)
    keep.append(len(points) - 1)

    result: list[ProfilePoint] = []
    for j, idx in enumerate(keep):
        incoming = slopes[idx - 1] if idx > 0 else None
        outgoing = slopes[idx] if idx < len(points) - 1 else None
        result.append(ProfilePoint(
            kind="BP" if j == 0 else "EP" if j == len(keep) - 1 else f"VIP {j}",
            sta=points[idx][0],
            elevation=points[idx][1],
            gradient_in=incoming,
            gradient_out=outgoing,
            delta_gradient=(outgoing - incoming if incoming is not None and outgoing is not None else None),
        ))
    return result


def export_csv(rows: list[ProfilePoint], output_path: str | Path) -> None:
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(ProfilePoint.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(row.as_dict() for row in rows)


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:+.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="DXF 계획 종단 VIP/구배 추출")
    parser.add_argument("dxf", help="converted_dxf.dxf 파일 경로")
    parser.add_argument("--layer", default="PLAN_PROFILE")
    parser.add_argument("--tolerance", type=float, default=1e-5, help="구배 변화 허용오차 (‰)")
    parser.add_argument("--csv", help="선택적 CSV 출력 경로")
    parser.add_argument("--json", help="선택적 JSON 출력 경로")
    parser.add_argument("--h", type=float, default=1)
    parser.add_argument("--v", type=float, default=1)
    parser.add_argument("--datum", type=float, default=0)
    parser.add_argument("--station-origin", type=float, default=0)
    parser.add_argument("--paper-mm", action="store_true", help="도면 좌표 mm 및 H/V 축척 사용")
    args = parser.parse_args()

    scale = ProfileScale(args.h, args.v, args.datum, args.station_origin, "paper_mm" if args.paper_mm else "legacy")
    rows = extract_profile(args.dxf, layer=args.layer, gradient_tolerance=args.tolerance, scale=scale)
    print(f"{'구분':<8} {'STA':>12} {'EL':>12} {'진입(‰)':>12} {'진출(‰)':>12} {'변화(‰)':>12}")
    for row in rows:
        print(f"{row.kind:<8} {row.sta:12.3f} {row.elevation:12.3f} "
              f"{_fmt(row.gradient_in):>12} {_fmt(row.gradient_out):>12} "
              f"{_fmt(row.delta_gradient):>12}")
    if args.csv:
        export_csv(rows, args.csv)
        print(f"CSV 저장 완료: {args.csv}")
    if args.json:
        Path(args.json).write_text(
            json.dumps([row.as_dict() for row in rows], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON 저장 완료: {args.json}")


if __name__ == "__main__":
    main()
