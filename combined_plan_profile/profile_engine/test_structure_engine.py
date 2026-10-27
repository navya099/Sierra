import unittest
from .structure_engine import StructureSettings, detect_structures, export_csv, load_manual_csv
from .vertical_curve import VerticalAlignment
from tempfile import TemporaryDirectory
from pathlib import Path

class StructureEngineTests(unittest.TestCase):
    def test_tunnel(self):
        a=VerticalAlignment([(0,0),(300,0)])
        g=[(0,0),(150,50),(300,0)]
        s=detect_structures(g,a)
        self.assertEqual(len(s),1)
        self.assertEqual(s[0].kind,'TUNNEL')
        self.assertAlmostEqual(s[0].max_height,50)
        self.assertAlmostEqual(s[0].length,258)
        self.assertAlmostEqual(s[0].start_sta,21)
        self.assertAlmostEqual(s[0].end_sta,279)
    def test_tunnel_height_change_recalculates_boundaries(self):
        a=VerticalAlignment([(0,0),(300,0)])
        g=[(0,0),(150,50),(300,0)]
        low=detect_structures(g,a,StructureSettings(tunnel_body_height=9,tunnel_bottom_offset=2))
        high=detect_structures(g,a,StructureSettings(tunnel_body_height=13,tunnel_bottom_offset=2))
        self.assertAlmostEqual(low[0].start_sta,21)
        self.assertAlmostEqual(high[0].start_sta,33)
        self.assertLess(high[0].length,low[0].length)

    def test_tunnel_min_cover(self):
        a=VerticalAlignment([(0,0),(300,0)])
        g=[(0,0),(150,50),(300,0)]
        result=detect_structures(g,a,StructureSettings(tunnel_min_cover=3))
        self.assertAlmostEqual(result[0].start_sta,30)
        self.assertAlmostEqual(result[0].end_sta,270)

    def test_short_after_trim_is_rejected(self):
        a=VerticalAlignment([(0,0),(110,0)])
        g=[(0,0),(55,50),(110,0)]
        self.assertEqual(detect_structures(g,a),[])

    def test_bridge_unchanged_with_tunnel_dimensions(self):
        a=VerticalAlignment([(0,30),(300,30)])
        g=[(0,30),(150,0),(300,30)]
        x=detect_structures(g,a,StructureSettings(tunnel_body_height=15,tunnel_min_cover=4))
        self.assertAlmostEqual(x[0].start_sta,25)
        self.assertAlmostEqual(x[0].end_sta,275)

    def test_bridge(self):
        a=VerticalAlignment([(0,30),(300,30)])
        g=[(0,30),(150,0),(300,30)]
        s=detect_structures(g,a)
        self.assertEqual(s[0].kind,'BRIDGE')
        self.assertAlmostEqual(s[0].max_height,30)
    def test_short_rejected(self):
        a=VerticalAlignment([(0,0),(80,0)])
        self.assertEqual(detect_structures([(0,0),(40,80),(80,0)],a),[])
    def test_threshold(self):
        a=VerticalAlignment([(0,0),(300,0)])
        self.assertEqual(detect_structures([(0,0),(150,39),(300,0)],a),[])
    def test_curve_double_crossing(self):
        a=VerticalAlignment([(0,0),(150,15),(300,0)],{1:300})
        g=[(0,0),(300,0)]
        s=detect_structures(g,a,StructureSettings(0,0,0,0,0,0))
        self.assertEqual(len(s),1)
        self.assertEqual(s[0].kind,'BRIDGE')
        self.assertAlmostEqual(s[0].start_sta,0)
        self.assertAlmostEqual(s[0].end_sta,300)
    def test_bridge_trimmed_to_five_meters(self):
        a=VerticalAlignment([(0,30),(300,30)])
        g=[(0,30),(150,0),(300,30)]
        found=detect_structures(g,a)
        self.assertEqual(len(found),1)
        self.assertAlmostEqual(found[0].start_sta,25,places=4)
        self.assertAlmostEqual(found[0].end_sta,275,places=4)
        self.assertEqual(found[0].name,'B1')

    def test_bridge_depth_overrides_boundary(self):
        a=VerticalAlignment([(0,30),(300,30)])
        g=[(0,30),(150,0),(300,30)]
        cfg=StructureSettings(girder_clearance_depth=10)
        found=detect_structures(g,a,cfg)
        self.assertAlmostEqual(found[0].start_sta,50,places=4)
        self.assertAlmostEqual(found[0].end_sta,250,places=4)

    def test_manual_structure_not_trimmed(self):
        from structure_engine import StructureSegment
        segment=StructureSegment('BRIDGE',0,300,30,150,'MANUAL','Custom')
        self.assertEqual(segment.start_sta,0)
        self.assertEqual(segment.name,'Custom')

    def test_manual_csv(self):
        from structure_engine import StructureSegment
        with TemporaryDirectory() as d:
            path=Path(d)/'test.csv'
            export_csv([StructureSegment('TUNNEL',100,200,45,150)],path)
            x=load_manual_csv(path)
            self.assertEqual(x[0].source,'MANUAL')
            self.assertEqual(x[0].length,100)
    def test_invalid_settings(self):
        with self.assertRaises(ValueError):
            StructureSettings(tunnel_cut_threshold=-1)

if __name__=='__main__':
    unittest.main()
