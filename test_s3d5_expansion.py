import unittest
from profile_presets.loader import load_preset, validate_preset
from profile_drawing import DrawingOptions, create_profile_drawing
from profile_transform import DrawingMode
from test_s3d2_preset_dxf import TestS3D2

class ExpansionTests(unittest.TestCase):
    def test_all_six_opt_in_disabled(self):
        for mode in ('cad','report'):
            for h,v in ((1000,400),(5000,1000),(25000,5000)):
                p=load_preset(mode,h,v)
                self.assertFalse(p['layout']['expansion']['enabled'])
    def test_invalid_expansion(self):
        p=load_preset('cad',5000,1000)
        p['layout']['expansion']['profile_plot_height']=-10
        with self.assertRaises(ValueError): validate_preset(p)
    def test_expanded_band_and_upper_bound(self):
        import ezdxf
        f=TestS3D2(methodName='test_baseline_exact');f.setUp()
        try:
            p=load_preset('cad',5000,1000)
            p['layout']['expansion'].update(enabled=True,band_height_factor=5,
                label_column_width=200,text_height_factor=5,
                profile_plot_height=500,use_placement_clearance=True)
            p['layout']['placement'].update(band_to_profile_gap=30,
                reserved_structure_depth=250,structure_clearance=10)
            out=f.root/'d5.dxf'
            result=create_profile_drawing(f.src,out,DrawingOptions(
                drawing_mode=DrawingMode.CAD,horizontal_scale=5000,
                vertical_scale=1000,layout_preset=p))
            self.assertEqual(result['plot_lower_y'],740) # 450+30+250+10
            self.assertEqual(result['plot_upper_y'],1240)
            self.assertEqual(p['layout']['band']['alignment_height'],20) # no mutation
            band=[e for e in ezdxf.readfile(out).modelspace().query('LINE')
                  if e.dxf.layer=='PROFILE_BAND']
            self.assertTrue(any(abs(e.dxf.start.y-450)<1e-7 or abs(e.dxf.end.y-450)<1e-7 for e in band))
        finally:f.tearDown()
    def test_report_independent(self):
        a=load_preset('cad',5000,1000)
        b=load_preset('report',5000,1000)
        a['layout']['expansion']['label_column_width']=321
        self.assertEqual(b['layout']['expansion']['label_column_width'],200)
