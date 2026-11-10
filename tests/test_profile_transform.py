import unittest
from profile_transform import ProfileTransform
from profile_layout import ProfileLayout

class RegressionTest(unittest.TestCase):
    def test_matches_legacy_layout(self):
        layout = ProfileLayout(origin_x=123, origin_y=77)
        for h,v in [(1000,400),(5000,1000),(25000,5000),(750,300),(12000,2500)]:
            tr = ProfileTransform(h,v,layout.origin_x,layout.origin_y,layout.label_column_width,10,150)
            for sta in (0,20,700,1234.5):
                self.assertAlmostEqual(tr.station_x(sta,0),layout.station_x(sta,0,h)+10)
            for el in (0,15.5,88.8):
                self.assertAlmostEqual(tr.elevation_y(el,10),layout.elevation_y(el,10,150,v))
            self.assertAlmostEqual(tr.vertical_exaggeration,h/v)
    def test_invalid(self):
        for h,v in [(0,400),(1000,-1),(float('nan'),400)]:
            with self.assertRaises(ValueError): ProfileTransform(h,v)
if __name__=='__main__': unittest.main()
