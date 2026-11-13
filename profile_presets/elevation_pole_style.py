
"""REG2-R5-A-2-1: Elevation Pole style definition and validation.

No DXF rendering, coordinate transformation, or preset mutation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ElevationPoleSolidStyle:
    width: float
    stripe_height: float
    color: int


@dataclass(frozen=True, slots=True)
class ElevationPoleLabelStyle:
    interval_m: float
    text_height: float
    leader_length: float


@dataclass(frozen=True, slots=True)
class ElevationPolePlacementStyle:
    bottom: str
    top: str


@dataclass(frozen=True, slots=True)
class ElevationPoleStyle:
    enabled: bool
    solid: ElevationPoleSolidStyle
    labels: ElevationPoleLabelStyle
    placement: ElevationPolePlacementStyle


def _object(value: Any, path: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path}: object required")
    return value


def _keys(value: Mapping, expected: set[str], path: str) -> None:
    if set(value) != expected:
        raise ValueError(
            f"{path}: missing={sorted(expected - set(value))}, "
            f"extra={sorted(set(value) - expected)}"
        )


def _positive(value: Any, path: str) -> float:
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{path}: finite positive number required")
    return float(value)


def _color(value: Any, path: str) -> int:
    if type(value) is not int or not 1 <= value <= 255:
        raise ValueError(f"{path}: ACI color 1..255 required")
    return value


def elevation_pole_style_from_preset(
    preset: Mapping[str, Any],
) -> ElevationPoleStyle | None:
    """Return None when no elevation pole style is configured.

    Missing style preserves the legacy renderer.
    Invalid explicit style raises ValueError.
    """

    root = _object(preset, "preset")

    if root.get("schema_version") != 2:
        return None

    layout = _object(root.get("layout"), "layout")
    annotations = layout.get("annotations")

    if annotations is None:
        return None

    annotations = _object(annotations, "layout.annotations")

    if "elevation_pole" not in annotations:
        return None

    path = "layout.annotations.elevation_pole"
    raw = _object(annotations["elevation_pole"], path)

    _keys(raw, {"enabled", "solid", "labels", "placement"}, path)

    if type(raw["enabled"]) is not bool:
        raise ValueError(f"{path}.enabled: boolean required")

    solid = _object(raw["solid"], f"{path}.solid")
    labels = _object(raw["labels"], f"{path}.labels")
    placement = _object(raw["placement"], f"{path}.placement")

    _keys(
        solid,
        {"width", "stripe_height", "color"},
        f"{path}.solid",
    )
    _keys(
        labels,
        {"interval_m", "text_height", "leader_length"},
        f"{path}.labels",
    )
    _keys(
        placement,
        {"bottom", "top"},
        f"{path}.placement",
    )

    if placement["bottom"] != "band_top":
        raise ValueError(f"{path}.placement.bottom: expected band_top")

    if placement["top"] != "plot_upper":
        raise ValueError(f"{path}.placement.top: expected plot_upper")

    return ElevationPoleStyle(
        enabled=raw["enabled"],
        solid=ElevationPoleSolidStyle(
            width=_positive(solid["width"], f"{path}.solid.width"),
            stripe_height=_positive(
                solid["stripe_height"], f"{path}.solid.stripe_height"
            ),
            color=_color(solid["color"], f"{path}.solid.color"),
        ),
        labels=ElevationPoleLabelStyle(
            interval_m=_positive(
                labels["interval_m"], f"{path}.labels.interval_m"
            ),
            text_height=_positive(
                labels["text_height"], f"{path}.labels.text_height"
            ),
            leader_length=_positive(
                labels["leader_length"], f"{path}.labels.leader_length"
            ),
        ),
        placement=ElevationPolePlacementStyle(
            bottom=placement["bottom"],
            top=placement["top"],
        ),
    )
