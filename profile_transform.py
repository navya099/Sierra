"""Sierra S3-A: coordinate policy for CAD creation and report output.

Source station/elevation values are metres. CAD uses 1 DXF unit per metre in
X; report uses paper millimetres. Offsets are in the selected output units.
The default REPORT+exaggerated policy reproduces the S1 transform exactly.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math


class DrawingMode(str, Enum):
    CAD = 'cad'
    REPORT = 'report'


@dataclass(frozen=True)
class ProfileTransform:
    horizontal_scale: float = 1000.0
    vertical_scale: float = 400.0
    origin_x: float = 0.0
    origin_y: float = 0.0
    label_column_width: float = 40.0
    start_margin: float = 10.0
    plot_lower_y: float = 150.0
    mode: DrawingMode = DrawingMode.REPORT
    vertical_exaggeration_enabled: bool = True

    def __post_init__(self):
        if not all(math.isfinite(v) and v > 0 for v in (self.horizontal_scale, self.vertical_scale)):
            raise ValueError('H/V scales must be finite and positive')
        try:
            mode = DrawingMode(self.mode)
        except (ValueError, TypeError) as exc:
            raise ValueError('mode must be cad or report') from exc
        object.__setattr__(self, 'mode', mode)

    @property
    def vertical_exaggeration(self) -> float:
        return (self.horizontal_scale / self.vertical_scale
                if self.vertical_exaggeration_enabled else 1.0)

    @property
    def x_units_per_metre(self) -> float:
        return 1.0 if self.mode is DrawingMode.CAD else 1000.0 / self.horizontal_scale

    @property
    def y_units_per_metre(self) -> float:
        return self.x_units_per_metre * self.vertical_exaggeration

    def station_x(self, sta: float, sheet_start_sta: float) -> float:
        return (self.origin_x + self.label_column_width + self.start_margin
                + (sta - sheet_start_sta) * self.x_units_per_metre)

    def elevation_y(self, elevation: float, datum_el: float) -> float:
        return (self.origin_y + self.plot_lower_y
                + (elevation - datum_el) * self.y_units_per_metre)
