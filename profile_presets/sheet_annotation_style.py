"""REG2-R3-B2: Sheet annotation style.

All text heights represent final DXF modelspace heights.
The sheet generator converts them to pre-scale heights
before applying its existing paper_factor.
"""

from dataclasses import dataclass
from typing import Mapping, Any


@dataclass(frozen=True, slots=True)
class SheetAnnotationStyle:
    title_height: float
    direction_height: float
    matchline_height: float
    north_height: float


def sheet_style_from_preset(
    preset: Mapping[str, Any],
) -> SheetAnnotationStyle:
    scale = float(preset["horizontal_scale"])
    factor = scale / 1000.0

    annotations = preset["layout"]["annotations"]
    raw = annotations.get("sheet")

    if raw is None:
        return SheetAnnotationStyle(
            title_height=4.0 * factor,
            direction_height=5.0 * factor,
            matchline_height=3.0 * factor,
            north_height=5.0 * factor,
        )

    return SheetAnnotationStyle(
        title_height=float(raw["title"]["text_height"]),
        direction_height=float(raw["direction"]["text_height"]),
        matchline_height=float(raw["matchline"]["text_height"]),
        north_height=float(raw["north"]["text_height"]),
    )