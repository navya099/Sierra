
"""REG2-R5-A-2-2: Elevation Pole preset integration tests."""

from copy import deepcopy

import pytest

from profile_presets.loader import load_preset, validate_preset
from profile_presets.elevation_pole_style import (
    elevation_pole_style_from_preset,
)


@pytest.mark.parametrize(
    "hscale,vscale,width,stripe,interval_m",
    [
        (1000, 400, 2.5, 10.0, 10.0),
        (5000, 1000, 12.5, 50.0, 50.0),
    ],
)
def test_builtin_elevation_pole(
    hscale, vscale, width, stripe, interval_m
):
    preset = load_preset("cad", hscale, vscale)
    style = elevation_pole_style_from_preset(preset)

    assert style is not None
    assert style.enabled is True
    assert style.solid.width == width
    assert style.solid.stripe_height == stripe
    assert style.labels.interval_m == interval_m


@pytest.mark.parametrize(
    "hscale,vscale",
    [(1000, 400), (5000, 1000)],
)
def test_legacy_preset_still_valid(hscale, vscale):
    preset = load_preset("cad", hscale, vscale)
    old_preset = deepcopy(preset)

    del old_preset["layout"]["annotations"]["elevation_pole"]

    assert validate_preset(old_preset) is True
    assert elevation_pole_style_from_preset(old_preset) is None


def test_invalid_elevation_pole_rejected():
    preset = load_preset("cad", 5000, 1000)
    broken = deepcopy(preset)

    pole = broken["layout"]["annotations"]["elevation_pole"]
    pole["solid"]["stripe_height"] = 0

    with pytest.raises(ValueError):
        validate_preset(broken)


def test_unknown_elevation_pole_field_rejected():
    preset = load_preset("cad", 1000, 400)
    broken = deepcopy(preset)

    pole = broken["layout"]["annotations"]["elevation_pole"]
    pole["unexpected"] = 123

    with pytest.raises(ValueError):
        validate_preset(broken)
