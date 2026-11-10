"""S3-D7.2: independent curve amplitude, direction, compatibility and validation."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ezdxf
from alignment_band import draw_alignment_band
from profile_drawing import _text
from profile_presets.loader import validate_preset
from profile_presets.runtime import to_drawing_preset

ROOT = Path(__file__).resolve().parent.parent

class CurveOffsetTests(unittest.TestCase):
    def setUp(self):
        self.preset = json.loads((ROOT/'h5000_v1000_S3D7_2_user_baseline.json').read_text(encoding='utf-8'))

    def render(self, direction, signed_value, curve_offset, curve_type='simplecurve'):
        ip = dict(curve_start_sta_m=20, curve_end_sta_m=80, band_offset_mm=signed_value,
                  curve_type=curve_type, direction=direction, ia='20', radius_m=1000,
                  tl_m=20, cl_m=40, stations={'BC':20, 'EC':80})
        cfg = copy.deepcopy(self.preset['layout']['band']['alignment'])
        if curve_offset is None:
            cfg['diagram'].pop('curve_offset', None)
        else:
            cfg['diagram']['curve_offset'] = curve_offset
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'input.dxf'; source.touch()
            doc=ezdxf.new(); msp=doc.modelspace()
            with patch('alignment_band.extract_with_stations', return_value={'ips':[ip]}):
                draw_alignment_band(msp,source,0,100,lambda x:x,0,_text,None,alignment_settings=cfg)
            lines = [(e.dxf.layer,tuple(e.dxf.start),tuple(e.dxf.end)) for e in msp.query('LINE')]
            labels = [tuple(e.dxf.insert) for e in msp.query('TEXT[layer=="ALIGNMENT_ELEMENT_TEXT"]')]
            return lines, labels

    def test_default_equivalence_and_direction(self):
        for direction,offset in [('LEFT',-6),('RIGHT',6)]:
            with self.subTest(direction=direction):
                self.assertEqual(self.render(direction,offset,6),self.render(direction,offset,None))

    def test_amplitude_changes_curve_not_straight_and_labels_follow(self):
        for direction,old in [('LEFT',-6),('RIGHT',6)]:
            before,labels_before=self.render(direction,old,6)
            after,labels_after=self.render(direction,old,12)
            straight_before=[x for x in before if x[0]=='ALIGNMENT_STRAIGHT']
            straight_after=[x for x in after if x[0]=='ALIGNMENT_STRAIGHT']
            self.assertEqual(straight_before,straight_after)
            curve_y_before=[p[1] for _,a,b in before for p in (a,b) if abs(p[1]-40)>0.1]
            curve_y_after=[p[1] for _,a,b in after for p in (a,b) if abs(p[1]-40)>0.1]
            self.assertIn(40+old,curve_y_before)
            self.assertIn(40+(12 if old>0 else -12),curve_y_after)
            self.assertNotEqual(labels_before,labels_after)

    def test_zero_offset(self):
        lines,_=self.render('RIGHT',6,0)
        self.assertTrue(all(abs(p[1]-40)<1e-7 for _,a,b in lines for p in (a,b)))

    def test_validation_and_immutability(self):
        original=copy.deepcopy(self.preset)
        self.assertTrue(validate_preset(self.preset))
        self.assertEqual(to_drawing_preset(self.preset)['_s3d7_alignment']['diagram']['curve_offset'],6)
        self.assertEqual(self.preset,original)
        for value in (-1,True,'6',float('nan')):
            bad=copy.deepcopy(self.preset)
            bad['layout']['band']['alignment']['diagram']['curve_offset']=value
            with self.subTest(value=value),self.assertRaises(ValueError):validate_preset(bad)
        old=copy.deepcopy(self.preset)
        del old['layout']['band']['alignment']['diagram']['curve_offset']
        self.assertTrue(validate_preset(old))

if __name__=='__main__':unittest.main()
