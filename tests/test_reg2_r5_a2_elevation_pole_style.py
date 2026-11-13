
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from profile_presets.elevation_pole_style import (
    elevation_pole_style_from_preset,
)


def make_preset():
    return {
        "schema_version": 2,
        "layout": {
            "annotations": {
                "elevation_pole": {
                    "enabled": True,
                    "solid": {
                        "width": 12.5,
                        "stripe_height": 50.0,
                        "color": 7,
                    },
                    "labels": {
                        "interval_m": 50.0,
                        "text_height": 12.5,
                        "leader_length": 68.75,
                    },
                    "placement": {
                        "bottom": "band_top",
                        "top": "plot_upper",
                    },
                }
            }
        },
    }


def test_h5000_values():
    style = elevation_pole_style_from_preset(make_preset())
    assert style.solid.width == 12.5
    assert style.solid.stripe_height == 50.0
    assert style.labels.interval_m == 50.0


def test_missing_style():
    preset = make_preset()
    del preset["layout"]["annotations"]["elevation_pole"]
    assert elevation_pole_style_from_preset(preset) is None


def test_missing_annotations():
    preset = make_preset()
    del preset["layout"]["annotations"]
    assert elevation_pole_style_from_preset(preset) is None


def test_no_mutation():
    preset = make_preset()
    before = deepcopy(preset)
    elevation_pole_style_from_preset(preset)
    assert preset == before


def test_immutable():
    style = elevation_pole_style_from_preset(make_preset())
    with pytest.raises(FrozenInstanceError):
        style.solid.width = 20


@pytest.mark.parametrize(
    "field,value",
    [
        ("width", 0),
        ("width", -1),
        ("width", float("nan")),
        ("stripe_height", 0),
        ("color", 256),
    ],
)
def test_invalid_solid(field, value):
    preset = make_preset()
    pole = preset["layout"]["annotations"]["elevation_pole"]
    pole["solid"][field] = value
    with pytest.raises(ValueError):
        elevation_pole_style_from_preset(preset)


def test_invalid_placement():
    preset = make_preset()
    pole = preset["layout"]["annotations"]["elevation_pole"]
    pole["placement"]["bottom"] = "plot_lower"
    with pytest.raises(ValueError):
        elevation_pole_style_from_preset(preset)


def test_disabled_style():
    preset = make_preset()
    pole = preset["layout"]["annotations"]["elevation_pole"]
    pole["enabled"] = False
    assert elevation_pole_style_from_preset(preset).enabled is False
