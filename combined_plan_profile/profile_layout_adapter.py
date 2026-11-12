
"""REG2-R4-B1: combined-sheet profile preset placement."""

from copy import deepcopy

from .sheet_policy import make_sheet_policy


def make_combined_profile_preset(
    source_preset: dict,
    horizontal_scale: float,
    vertical_scale: float,
    sheet_length: float,
) -> dict:
    """Preserve absolute dimensions; relocate only the sheet origin."""

    policy = make_sheet_policy(
        horizontal_scale,
        vertical_scale,
        sheet_length,
    )

    preset = deepcopy(source_preset)

    # Source preset uses schema-v2 nested coordinates.
    if preset["schema_version"] != 2:
        raise ValueError(
            "REG2-R4-B1 requires a schema-v2 CAD preset"
        )

    origin = preset["layout"]["sheet"]["origin"]

    # H1000 combined-sheet origin: (35, 70).
    # Scale the placement coordinates, not the preset dimensions.
    origin["x"] = 35.0 * policy.paper_factor
    origin["y"] = 70.0 * policy.paper_factor

    return preset
