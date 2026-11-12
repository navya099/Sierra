from collections import Counter
from pathlib import Path

import ezdxf
import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "test_outputs" / "REG2-R3-B2"


@pytest.mark.parametrize(
    "folder,heights",
    [
        ("FINAL_H1000", (4, 5, 3, 5)),
        ("FINAL_H5000", (20, 25, 15, 25)),
        ("CUSTOM_H1000_FIX4", (7, 9, 6, 11)),
    ],
)
def test_sheet_annotation_heights(folder, heights):
    paths = list((OUTPUT / folder).glob("*.dxf"))

    if not paths:
        pytest.skip("DXF integration fixture not generated")

    assert len(paths) == 1

    doc = ezdxf.readfile(paths[0])
    title, direction, matchline, north = heights

    expected = {
        "ZPP_SHEET_ANNOTATION": Counter({
            float(title): 4,
            float(direction): 4,
        }),
        "ZPP_MATCHLINE_LABEL": Counter({
            float(matchline): 2,
        }),
        "ZPP_NORTH_ARROW": Counter({
            float(north): 1,
        }),
    }

    for layer, want in expected.items():
        actual = Counter(
            round(float(e.dxf.height), 6)
            for e in doc.modelspace().query("TEXT")
            if e.dxf.layer == layer
        )
        assert actual == want, (
            f"{folder}/{layer}: expected={want}, actual={actual}"
        )