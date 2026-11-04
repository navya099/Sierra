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

ROOT=Path(__file__).resolve().parent

class SimpleCurveElementTests(unittest.TestCase):
    def setUp(self):
        self.preset=json.loads((ROOT/'h5000_v1000_S3D7_5_user_baseline.json').read_text(encoding='utf-8'))

    def test_preset_valid(self):
        self.assertTrue(validate_preset(self.preset))

    def render(self,direction):
        cfg=self.preset['layout']['band']['alignment']
        ip={'curve_start_sta_m':20,'curve_end_sta_m':80,'band_offset_mm':6 if direction=='RIGHT' else -6,
            'curve_type':'simplecurve','direction':direction,'ia':'20','radius_m':1000,
            'tl_m':20,'cl_m':60,'stations':{'BC':20,'EC':80}}
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.dxf';source.touch()
            doc=ezdxf.new();msp=doc.modelspace()
            with patch('alignment_band.extract_with_stations',return_value={'ips':[ip]}):
                draw_alignment_band(msp,source,0,100,lambda sta:sta,0,_text,None,alignment_settings=cfg)
            return [(e.dxf.text,e.dxf.halign,e.dxf.insert.x,e.dxf.insert.y) for e in msp.query('TEXT[layer=="ALIGNMENT_ELEMENT_TEXT"]')]

    def test_right_curve(self):
        rows=self.render('RIGHT')
        self.assertEqual([r[0].split('=')[0] for r in rows],['BC','EC'])
        self.assertEqual([r[1] for r in rows],[2,0])
        self.assertEqual([r[2] for r in rows],[20,80])
        self.assertEqual([r[3] for r in rows],[40,40])

    def test_left_curve(self):
        rows=self.render('LEFT')
        self.assertEqual([r[1] for r in rows],[2,0])
        self.assertEqual([r[2] for r in rows],[20,80])
        self.assertEqual([r[3] for r in rows],[20,20])

    def test_independent_bc_offset(self):
        cfg=self.preset['layout']['band']['alignment']['text']['element_station']['placement']
        cfg['BC']['x_offset']=-5
        rows=self.render('RIGHT')
        self.assertEqual([r[2] for r in rows],[15,80])

if __name__=='__main__': unittest.main()
