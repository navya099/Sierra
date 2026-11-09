"""FIX2 combined-sheet layout policy. Geometry remains CAD 1:1."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class SheetPolicy:
    horizontal_scale: float
    vertical_scale: float
    sheet_length: float
    paper_factor: float
    plan_rect: tuple[float, float, float, float]
    profile_rect: tuple[float, float, float, float]


def make_sheet_policy(horizontal_scale: float, vertical_scale: float, sheet_length: float) -> SheetPolicy:
    for name, value in [('horizontal_scale',horizontal_scale),('vertical_scale',vertical_scale),('sheet_length',sheet_length)]:
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be a positive finite number')
    factor = horizontal_scale / 1000.0
    if factor < 1:
        raise ValueError('FIX2 initial policy only supports H >= 1000')
    return SheetPolicy(horizontal_scale, vertical_scale, sheet_length, factor,
                       tuple(v * factor for v in (35.,330.,811.,530.)),
                       tuple(v * factor for v in (35.,70.,811.,315.)))
