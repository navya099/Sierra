import copy
import tempfile
import unittest
from pathlib import Path
import ezdxf
from profile_presets.loader import validate_preset
from test_preset_fixture import load_preset
from profile_drawing import DrawingOptions, create_profile_drawing
from profile_transform import DrawingMode
from test_s3d2_preset_dxf import TestS3D2

class VisibilityTests(unittest.TestCase):
    def test_six_presets_policy_disabled(self):
        for mode in ('cad','report'):
            for h,v in ((1000,400),(5000,1000),(25000,5000)):
                p=load_preset(mode,h,v)
                self.assertFalse(p['visibility_policy']['enabled'])
                self.assertTrue(validate_preset(p))

    def test_invalid_policy_rejected(self):
        p=load_preset('cad',5000,1000)
        p['visibility_policy']['minor_grid']='false'
        with self.assertRaises(ValueError):validate_preset(p)

    def test_independent_mode_policies(self):
        a=load_preset('cad',5000,1000)
        b=load_preset('report',5000,1000)
        a['visibility_policy']['minor_grid']=False
        self.assertTrue(b['visibility_policy']['minor_grid'])

    def test_opt_in_filters_only_selected_layers(self):
        fixture=TestS3D2(methodName='test_baseline_exact')
        fixture.setUp()
        try:
            p=load_preset('cad',1000,400)
            opt=DrawingOptions(drawing_mode=DrawingMode.CAD,layout_preset=p)
            path=fixture.root/'d4_full.dxf'
            create_profile_drawing(fixture.src,path,opt)
            full=ezdxf.readfile(path).modelspace()
            layers={e.dxf.layer for e in full}
            self.assertIn('GROUND_PROFILE',layers)
            self.assertIn('PLAN_PROFILE',layers)
            p['visibility_policy'].update(enabled=True,ground_profile=False,minor_grid=False)
            filtered=fixture.root/'d4_filtered.dxf'
            create_profile_drawing(fixture.src,filtered,DrawingOptions(drawing_mode=DrawingMode.CAD,layout_preset=p))
            after={e.dxf.layer for e in ezdxf.readfile(filtered).modelspace()}
            self.assertNotIn('GROUND_PROFILE',after)
            self.assertNotIn('GRID_MINOR',after)
            self.assertIn('PLAN_PROFILE',after)
            self.assertIn('PROFILE_BAND',after)
        finally:fixture.tearDown()
