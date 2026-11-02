import unittest
from profile_transform import DrawingMode, ProfileTransform


class TestS3AModes(unittest.TestCase):
    def test_cad_x_invariant(self):
        for h, v in ((1000, 400), (5000, 1000), (25000, 5000)):
            t = ProfileTransform(horizontal_scale=h, vertical_scale=v, mode=DrawingMode.CAD)
            self.assertAlmostEqual(t.station_x(120, 100)-t.station_x(100, 100), 20)

    def test_cad_y_exaggeration(self):
        for h, v, expected in ((1000, 400, 50), (5000, 1000, 100), (25000, 5000, 100)):
            t = ProfileTransform(horizontal_scale=h, vertical_scale=v, mode='cad')
            self.assertAlmostEqual(t.elevation_y(120, 100)-t.elevation_y(100, 100), expected)

    def test_report_x_y(self):
        t = ProfileTransform(horizontal_scale=5000, vertical_scale=1000, mode='report')
        self.assertAlmostEqual(t.station_x(120, 100)-t.station_x(100, 100), 4)
        self.assertAlmostEqual(t.elevation_y(120, 100)-t.elevation_y(100, 100), 20)

    def test_exaggeration_off(self):
        for mode, expected in ((DrawingMode.CAD, 20), (DrawingMode.REPORT, 4)):
            t = ProfileTransform(horizontal_scale=5000, vertical_scale=1000, mode=mode,
                                 vertical_exaggeration_enabled=False)
            self.assertAlmostEqual(t.elevation_y(120, 100)-t.elevation_y(100, 100), expected)
            self.assertEqual(t.vertical_exaggeration, 1)

    def test_legacy_default(self):
        t = ProfileTransform()
        self.assertEqual(t.mode, DrawingMode.REPORT)
        self.assertAlmostEqual(t.station_x(700, 0), 750)
        self.assertAlmostEqual(t.elevation_y(120, 100), 200)
        self.assertEqual(t.vertical_exaggeration, 2.5)

    def test_invalid(self):
        for kwargs in ({'mode':'invalid'}, {'horizontal_scale':0}, {'vertical_scale':float('nan')}):
            with self.assertRaises(ValueError):
                ProfileTransform(**kwargs)


if __name__ == '__main__':
    unittest.main()
