import unittest
from structure_engine import StructureSettings, detect_structures, export_csv, load_manual_csv
from vertical_curve import VerticalAlignment
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
        self.assertAlmostEqual(s[0].length,300)
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
        s=detect_structures(g,a,StructureSettings(0,0,0,0))
        self.assertEqual(len(s),1)
        self.assertEqual(s[0].kind,'BRIDGE')
        self.assertAlmostEqual(s[0].start_sta,0)
        self.assertAlmostEqual(s[0].end_sta,300)
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
