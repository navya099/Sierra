
from combined_plan_profile.profile_layout_adapter import (
    make_combined_profile_preset,
)
from profile_presets.loader import load_preset
from profile_presets.runtime import to_drawing_preset


def test_h5000_origin_and_absolute_dimensions():
    source = load_preset("cad", 5000, 1000)

    result = make_combined_profile_preset(
        source, 5000, 1000, 3500
    )

    assert result["layout"]["sheet"]["origin"] == {
        "x": 175.0,
        "y": 350.0,
    }

    # Original preset must remain unchanged.
    assert source["layout"]["sheet"]["origin"] == {
        "x": 0,
        "y": 0,
    }

    drawing = to_drawing_preset(result)
    layout = drawing["layout"]

    assert layout["band"]["alignment_height"] == 80
    assert layout["band"]["ground_height"] == 80
    assert layout["band"]["design_height"] == 80
    assert layout["band"]["fill_height"] == 60
    assert layout["band"]["cut_height"] == 60

    assert layout["text"]["data_text_height"] == 15
    assert layout["text"]["label_text_height"] == 20

    assert layout["absolute_dimensions"]["profile"][
        "plot_height"
    ] == 500


def test_h1000_origin():
    source = load_preset("cad", 1000, 400)

    result = make_combined_profile_preset(
        source, 1000, 400, 700
    )

    assert result["layout"]["sheet"]["origin"] == {
        "x": 35.0,
        "y": 70.0,
    }
