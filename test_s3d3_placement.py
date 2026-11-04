import copy
import unittest
from profile_presets.loader import validate_preset
from test_preset_fixture import load_preset
from profile_drawing import DrawingOptions, create_profile_drawing
from profile_transform import DrawingMode
from test_s3d2_preset_dxf import TestS3D2

class PlacementTests(TestS3D2):
    def test_enabled_moves_profile_and_preserves_band(self):
        p=load_preset('cad',5000,1000)
        p['layout']['placement'].update(enabled=True,band_to_profile_gap=40,
                reserved_structure_depth=250,structure_clearance=20,profile_plot_height=180)
        result=create_profile_drawing(self.src,self.root/'p.dxf',DrawingOptions(
            drawing_mode=DrawingMode.CAD,horizontal_scale=5000,vertical_scale=1000,layout_preset=p))
        self.assertEqual(result['plot_lower_y'],400)
        self.assertEqual(result['plot_upper_y'],580)
        self.assertEqual(result['drawing_right'],760)
        self.assertTrue(result['layout_placement_enabled'])
        import ezdxf
        band=[e for e in ezdxf.readfile(self.root/'p.dxf').modelspace().query('LINE') if e.dxf.layer=='PROFILE_BAND']
        self.assertTrue(any(abs(e.dxf.start.y-90)<1e-7 for e in band))
    def test_disabled_matches_baseline(self):
        p=load_preset('report',1000,400)
        p['layout']['placement']['reserved_structure_depth']=5000
        result=create_profile_drawing(self.src,self.root/'base.dxf',DrawingOptions(layout_preset=p))
        self.assertEqual(result['plot_lower_y'],150)
    def test_invalid_placement_rejected(self):
        p=load_preset('cad',1000,400)
        p['layout']['placement']['reserved_structure_depth']=-1
        with self.assertRaises(ValueError):validate_preset(p)
