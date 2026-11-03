import copy
import unittest
import ezdxf
from test_preset_fixture import load_preset
from test_s3d2_preset_dxf import TestS3D2, entities
from profile_presets.loader import validate_preset
from profile_drawing import DrawingOptions, create_profile_drawing

class AnnotationDimensionsTests(unittest.TestCase):
    def test_validation(self):
        p=load_preset('cad',5000,1000)
        p['layout']['annotations']={'enabled':True, **{
            'datum_label_dx':11,'datum_label_dy':12,'datum_break_kink_dy':3,
            'alignment_station_top_inset':3,'vip_elevation_text_height':2.4,
            'vip_caption_text_height':2.4,'vip_caption_gap_factor':0.6,
            'curve_ordinate_offset':20,'curve_endpoint_text_offset':10,
            'curve_endpoint_line_height':26,'curve_text_height':2.4,
            'vip_distance_text_offset':2,'vip_distance_text_height':2.4,
            'vip_arrow_half_height':0.75,'vip_arrow_length':1.25,
            'grade_text_height':10,'distance_text_height':5}}
        self.assertTrue(validate_preset(p))
        p['layout']['annotations']['curve_text_height']=-1
        with self.assertRaises(ValueError):validate_preset(p)

    def test_opt_in_and_no_mutation(self):
        t=TestS3D2('test_baseline_exact');t.setUp()
        try:
            p=load_preset('cad',5000,1000)
            p['layout']['annotations']={'enabled':False, **{
                'datum_label_dx':11,'datum_label_dy':12,'datum_break_kink_dy':3,
                'alignment_station_top_inset':3,'vip_elevation_text_height':2.4,
                'vip_caption_text_height':2.4,'vip_caption_gap_factor':0.6,
                'curve_ordinate_offset':20,'curve_endpoint_text_offset':10,
                'curve_endpoint_line_height':26,'curve_text_height':2.4,
                'vip_distance_text_offset':2,'vip_distance_text_height':2.4,
                'vip_arrow_half_height':0.75,'vip_arrow_length':1.25,
                'grade_text_height':10,'distance_text_height':5}}
            base=t.root/'base.dxf'; changed=t.root/'changed.dxf'
            opts=lambda:DrawingOptions(drawing_mode='cad',horizontal_scale=5000,vertical_scale=1000,layout_preset=p)
            create_profile_drawing(t.src,base,opts())
            p['layout']['annotations']['enabled']=True
            p['layout']['annotations']['grade_text_height']=17
            p['layout']['annotations']['distance_text_height']=9
            before=copy.deepcopy(p)
            create_profile_drawing(t.src,changed,opts())
            self.assertEqual(p,before)
            a=ezdxf.readfile(base).modelspace();b=ezdxf.readfile(changed).modelspace()
            grades_a=[e.dxf.height for e in a.query('TEXT') if e.dxf.layer=='VIP_ANNOTATION']
            grades_b=[e.dxf.height for e in b.query('TEXT') if e.dxf.layer=='VIP_ANNOTATION']
            self.assertTrue(grades_a)
            self.assertIn(17,grades_b)
            self.assertIn(9,grades_b)
            self.assertNotEqual(grades_a,grades_b)
        finally:t.tearDown()

    def test_disabled_baseline(self):
        t=TestS3D2('test_baseline_exact');t.setUp()
        try:
            p=load_preset('cad',5000,1000)
            p.pop('visibility_policy',None)
            a=t.root/'one.dxf';b=t.root/'two.dxf'
            opts=lambda:DrawingOptions(drawing_mode='cad',horizontal_scale=5000,vertical_scale=1000,layout_preset=p)
            create_profile_drawing(t.src,a,opts())
            p['layout'].pop('annotations',None)
            create_profile_drawing(t.src,b,opts())
            self.assertEqual(entities(a),entities(b))
        finally:t.tearDown()
