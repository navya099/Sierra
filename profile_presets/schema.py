"""S3-D1 data contract. No drawing-engine changes in this phase."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Mode = Literal['cad', 'report']
Standard = Literal['detailed', 'simplified', 'overview']

@dataclass(frozen=True)
class PresetKey:
    mode: Mode
    horizontal_scale: int
    vertical_scale: int

    @property
    def filename(self) -> str:
        return f'h{self.horizontal_scale}_v{self.vertical_scale}.json'
