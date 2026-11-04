import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ezdxf
from ezdxf.enums import TextEntityAlignment
from alignment_band import draw_alignment_band
from profile_presets.loader import validate_preset
from profile_drawing import _text
ROOT=Path(__file__).resolve().parent

class ElementPlacementTests(unittest.TestCase):
    def setUp(self):
        self.preset=json.loads((ROOT/'h5000_v1000_S3D7_3_user_baseline.json').read_text(encoding='utf-8'))

    def test_preset_validation(self):
        self.assertTrue(validate_preset(self.preset))

    def test_invalid_alignment(self):
        preset=copy.deepcopy(self.preset)
        preset['layout']['band']['alignment']['text']['element_station']['placement']['SP']['align']='MIDDLE'
        with self.assertRaises(ValueError): validate_preset(preset)

    def test_element_placement(self):
        ip={'curve_start_sta_m':0,'curve_end_sta_m':100,'band_offset_mm':6,
            'curve_type':'spiral','direction':'RIGHT','ia':'20','radius_m':1000,
            'tl_m':20,'cl_m':40,'stations':{'SP':10,'PC':30,'CP':70,'PS':90}}
        cfg=self.preset['layout']['band']['alignment']
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.dxf';source.touch()
            doc=ezdxf.new();msp=doc.modelspace()
            with patch('alignment_band.extract_with_stations',return_value={'ips':[ip]}):
                draw_alignment_band(msp,source,0,100,lambda sta:sta,0,_text,None,alignment_settings=cfg)
            entities=list(msp.query('TEXT[layer=="ALIGNMENT_ELEMENT_TEXT"]'))
            self.assertEqual(len(entities),4)
            self.assertEqual([round(e.dxf.insert.x,4) for e in entities],[10,30,70,90])
            self.assertEqual([e.dxf.halign for e in entities],[2,0,0,2])

    def test_legacy_fallback(self):
        cfg=copy.deepcopy(self.preset['layout']['band']['alignment'])
        cfg['text'].pop('element_station')
        ip={'curve_start_sta_m':0,'curve_end_sta_m':100,'band_offset_mm':6,
            'curve_type':'simplecurve','direction':'RIGHT','ia':'20','radius_m':1000,
            'tl_m':20,'cl_m':40,'stations':{'BC':20,'EC':80}}
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.dxf';source.touch()
            doc=ezdxf.new();msp=doc.modelspace()
            with patch('alignment_band.extract_with_stations',return_value={'ips':[ip]}):
                draw_alignment_band(msp,source,0,100,lambda sta:sta,0,_text,None,alignment_settings=cfg)
            entities=list(msp.query('TEXT[layer=="ALIGNMENT_ELEMENT_TEXT"]'))
            self.assertEqual([e.dxf.insert.x for e in entities],[21.5,81.5])
            self.assertTrue(all(e.dxf.halign==0 for e in entities))

if __name__=='__main__': unittest.main()
