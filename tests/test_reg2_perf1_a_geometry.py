"""Regression parity tests; do not alter legacy implementations in PERF1-A."""
import math
import unittest

import ezdxf
from plan_geometry import read_fl, position_at, position_and_tangent_at
from final_plan_vip import read_fl as legacy_final_read_fl
from final_plan_vip import position_at as legacy_final_position
from combined_plan_profile.combined_plan_profile_v1_7_core import (
    position_at as legacy_combined_position,
)


def make_doc(points, *, closed=False, bulge=0.0):
    doc = ezdxf.new()
    doc.modelspace().add_lwpolyline(
        [(x, y, bulge if i == 0 else 0.0) for i, (x, y) in enumerate(points)],
        format="xyb", close=closed, dxfattribs={"layer": "FL"}
    )
    return doc


class GeometryParity(unittest.TestCase):
    def test_cleaning_and_distance_parity(self):
        for points in [
            [(0, 0), (10, 0), (10, 10)],
            [(0, 0), (0, 0), (3, 4), (3, 4), (6, 8)],
            [(1000, 2000), (1100, 2000), (1100, 2200)],
        ]:
            doc = make_doc(points)
            self.assertEqual(read_fl(doc), legacy_final_read_fl(doc))

    def test_position_and_tangent_parity(self):
        doc = make_doc([(0, 0), (10, 0), (10, 10), (20, 10)])
        points, distances = read_fl(doc)
        for sta in (0, 1, 9.999, 10, 10.001, 15, 20, 30):
            actual = position_and_tangent_at(sta, points, distances)
            expected = legacy_final_position(sta, points, distances)
            for a, b in zip(actual[0] + actual[1], expected[0] + expected[1]):
                self.assertAlmostEqual(a, b, places=10)
            self.assertEqual(position_at(sta, points, distances),
                             legacy_combined_position(sta, points, distances))

    def test_validation(self):
        with self.assertRaises(ValueError):
            read_fl(ezdxf.new())
        with self.assertRaises(ValueError):
            read_fl(make_doc([(0, 0), (0, 0)]))
        with self.assertRaises(ValueError):
            read_fl(make_doc([(0, 0), (10, 0)], closed=True))
        with self.assertRaises(ValueError):
            read_fl(make_doc([(0, 0), (10, 0)], bulge=0.1))

    def test_station_bounds(self):
        points, distances = read_fl(make_doc([(0, 0), (10, 0)]))
        with self.assertRaises(ValueError):
            position_and_tangent_at(-0.01, points, distances)
        with self.assertRaises(ValueError):
            position_and_tangent_at(10.01, points, distances)
        self.assertEqual(position_at(10, points, distances), (10, 0))


if __name__ == "__main__":
    unittest.main()
