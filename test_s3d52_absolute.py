import unittest
import ezdxf
from profile_presets.loader import load_preset, validate_preset
from profile_drawing import DrawingOptions, create_profile_drawing
from test_s3d2_preset_dxf import TestS3D2, entities

class AbsoluteDimensionTests(unittest.TestCase):
    def test_six_independent(self):
        for mode in ('cad','report'):
            for h,v in ((1000,400),(5000,1000),(25000,5000)):
                p=load_preset(mode,h,v)
                self.assertTrue(validate_preset(p))
                self.assertFalse(p['layout']['absolute_dimensions']['enabled'])
    def test_legacy_baseline(self):
        t=TestS3D2('test_baseline_exact');t.setUp()
        try:
            for mode in ('cad','report'):
                o=DrawingOptions(drawing_mode=mode,horizontal_scale=1000,vertical_scale=400)
                p=load_preset(mode,1000,400)
                a=t.root/'a.dxf';b=t.root/'b.dxf'
                create_profile_drawing(t.src,a,o)
                create_profile_drawing(t.src,b,DrawingOptions(drawing_mode=mode,layout_preset=p))
                self.assertEqual(entities(a),entities(b))
        finally:t.tearDown()
    def test_absolute_band_graph(self):
        t=TestS3D2('test_baseline_exact');t.setUp()
        try:
            p=load_preset('cad',5000,1000)
            p['layout']['absolute_dimensions']['enabled']=True
            out=t.root/'absolute.dxf'
            r=create_profile_drawing(t.src,out,DrawingOptions(drawing_mode='cad',horizontal_scale=5000,vertical_scale=1000,layout_preset=p))
            self.assertEqual(r['plot_lower_y'],740)
            self.assertEqual(r['plot_upper_y'],1240)
            self.assertEqual(p['layout']['band']['alignment_height'],20)
            band=[e for e in ezdxf.readfile(out).modelspace().query('LINE') if e.dxf.layer=='PROFILE_BAND']
            self.assertTrue(any(abs(e.dxf.start.y-450)<1e-8 for e in band))
            p['layout']['absolute_dimensions']['band']['alignment_height']=130
            r2=create_profile_drawing(t.src,t.root/'changed.dxf',DrawingOptions(drawing_mode='cad',horizontal_scale=5000,vertical_scale=1000,layout_preset=p))
            self.assertEqual(r2['plot_lower_y'],770)
        finally:t.tearDown()
    def test_invalid_absolute(self):
        p=load_preset('cad',5000,1000)
        p['layout']['absolute_dimensions']['text']['data_text_height']=-1
        with self.assertRaises(ValueError):validate_preset(p)
    def test_report_independence(self):
        a=load_preset('cad',5000,1000)
        b=load_preset('report',5000,1000)
        a['layout']['absolute_dimensions']['band']['ground_height']=999
        self.assertNotEqual(a['layout']['absolute_dimensions']['band']['ground_height'],b['layout']['absolute_dimensions']['band']['ground_height'])

if __name__=='__main__':unittest.main()
