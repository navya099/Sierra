"""Coordinate transform for railway longitudinal profiles.

Legacy mode: DXF drawing units are real metres (X=STA, Y=EL).
Paper mode: DXF drawing units are millimetres at 1:H horizontally,
1:V vertically. A datum and station origin may be used to reduce offsets.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ProfileScale:
    horizontal: float = 1.0
    vertical: float = 1.0
    datum: float = 0.0
    station_origin: float = 0.0
    mode: str = 'legacy'  # 'legacy' or 'paper_mm'

    def __post_init__(self):
        if self.mode not in ('legacy', 'paper_mm'):
            raise ValueError('mode는 legacy 또는 paper_mm이어야 합니다.')
        if not all(math.isfinite(v) for v in (self.horizontal, self.vertical, self.datum, self.station_origin)):
            raise ValueError('축척과 기준점은 유한한 숫자여야 합니다.')
        if self.horizontal <= 0 or self.vertical <= 0:
            raise ValueError('수평·수직 축척은 양수여야 합니다.')

    @property
    def x_factor(self) -> float:
        return 1.0 if self.mode == 'legacy' else self.horizontal / 1000.0

    @property
    def y_factor(self) -> float:
        return 1.0 if self.mode == 'legacy' else self.vertical / 1000.0

    def to_real(self, x: float, y: float) -> tuple[float, float]:
        if self.mode == 'legacy':
            return float(x), float(y)
        return self.station_origin + float(x) * self.x_factor, self.datum + float(y) * self.y_factor

    def to_dxf(self, sta: float, el: float) -> tuple[float, float]:
        if self.mode == 'legacy':
            return float(sta), float(el)
        return (float(sta) - self.station_origin) / self.x_factor, (float(el) - self.datum) / self.y_factor

    def convert_points_to_real(self, points):
        return [self.to_real(x, y) for x, y in points]

    def convert_points_to_dxf(self, points):
        return [self.to_dxf(sta, el) for sta, el in points]


PRESETS = {
    '기존 1:1 (m 좌표)': ('legacy', 1, 1),
    '실시설계 H1000 V400': ('paper_mm', 1000, 400),
    '기본계획·예타 H5000 V1000': ('paper_mm', 5000, 1000),
    '국가사업구상 H25000 V5000': ('paper_mm', 25000, 5000),
    '사용자 지정': ('paper_mm', 5000, 1000),
}
