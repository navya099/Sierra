"""Sierra S1: single authority for profile output coordinate transforms.

Input: station/elevation in real metres. Output: current profile drawing units.
The default reproduces the existing paper-mm engine; no coordinate policy is changed.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class ProfileTransform:
    horizontal_scale: float = 1000.0
    vertical_scale: float = 400.0
    origin_x: float = 0.0
    origin_y: float = 0.0
    label_column_width: float = 40.0
    start_margin: float = 10.0
    plot_lower_y: float = 150.0

    def __post_init__(self):
        if not all(math.isfinite(v) and v > 0 for v in (self.horizontal_scale, self.vertical_scale)):
            raise ValueError('H/V scales must be finite and positive')

    @property
    def vertical_exaggeration(self) -> float:
        return self.horizontal_scale / self.vertical_scale

    def station_x(self, sta: float, sheet_start_sta: float) -> float:
        return (self.origin_x + self.label_column_width + self.start_margin
                + (sta - sheet_start_sta) * 1000.0 / self.horizontal_scale)

    def elevation_y(self, elevation: float, datum_el: float) -> float:
        return (self.origin_y + self.plot_lower_y
                + (elevation - datum_el) * 1000.0 / self.vertical_scale)
