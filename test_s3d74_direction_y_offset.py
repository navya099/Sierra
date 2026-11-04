import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ezdxf
from alignment_band import draw_alignment_band
from profile_drawing import _text
from profile_presets.loader import validate_preset

ROOT = Path(__file__).resolve().parent

class DirectionYOffsetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preset = json.loads((ROOT/'h5000_v1000_S3D7_4_user_baseline.json').read_text(encoding='utf-8'))

    def render(self, direction, config):
        ip = {'curve_start_sta_m':0, 'curve_end_sta_m':100,
              'band_offset_mm':6 if direction=='RIGHT' else -6,
              'curve_type':'spiral', 'direction':direction, 'ia':'20',
              'radius_m':1000, 'tl_m':20, 'cl_m':40,
              'stations':{'SP':0, 'PC':30, 'CP':70, 'PS':100}}
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.dxf'; source.touch()
            doc=ezdxf.new(); msp=doc.modelspace()
            with patch('alignment_band.extract_with_stations', return_value={'ips':[ip]}):
                draw_alignment_band(msp, source, 0, 100, lambda sta:sta, 0, _text, None, alignment_settings=config)
            return {e.dxf.text.split('=')[0]:e.dxf.insert.y for e in msp.query('TEXT[layer=="ALIGNMENT_ELEMENT_TEXT"]')}

    def test_valid_preset(self):
        self.assertTrue(validate_preset(self.preset))

    def test_right_has_no_y_offset(self):
        result=self.render('RIGHT', self.preset['layout']['band']['alignment'])
        self.assertAlmostEqual(result['PC'],60) # baseline 40 + curve 20 + offset 0
        self.assertAlmostEqual(result['CP'],60)

    def test_left_has_positive_y_offset(self):
        result=self.render('LEFT', self.preset['layout']['band']['alignment'])
        self.assertAlmostEqual(result['PC'],40) # baseline 40 - curve 20 + offset 20
        self.assertAlmostEqual(result['CP'],40)

    def test_legacy_fallback(self):
        cfg=copy.deepcopy(self.preset['layout']['band']['alignment'])
        del cfg['text']['element_station']['y_offset']
        self.assertAlmostEqual(self.render('RIGHT',cfg)['PC'],40)
        self.assertAlmostEqual(self.render('LEFT',cfg)['PC'],40)

    def test_invalid_direction_keys(self):
        cfg=copy.deepcopy(self.preset)
        cfg['layout']['band']['alignment']['text']['element_station']['y_offset']={'LEFT':20}
        with self.assertRaises(ValueError): validate_preset(cfg)

    def test_invalid_nonfinite_value(self):
        cfg=copy.deepcopy(self.preset)
        cfg['layout']['band']['alignment']['text']['element_station']['y_offset']['LEFT']=math.inf
        with self.assertRaises(ValueError): validate_preset(cfg)

if __name__=='__main__': unittest.main()
