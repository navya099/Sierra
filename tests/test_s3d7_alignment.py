"""S3-D7 alignment JSON and DXF text placement regression."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ezdxf
from alignment_band import draw_alignment_band
from profile_presets.loader import validate_preset
from profile_presets.runtime import to_drawing_preset
from profile_drawing import _text

ROOT = Path(__file__).resolve().parent.parent

class AlignmentD7Tests(unittest.TestCase):
    def setUp(self):
        self.preset = json.loads((ROOT/'h5000_v1000_schema_v2.json').read_text(encoding='utf-8'))

    def test_new_group_and_legacy_group(self):
        self.assertTrue(validate_preset(self.preset))
        p = to_drawing_preset(self.preset)
        self.assertEqual(p['_s3d7_alignment']['text']['curve_info_height'], 1.8)
        self.assertEqual(p['layout']['annotations']['alignment_station_top_inset'], 15)
        old = copy.deepcopy(self.preset)
        old['layout']['band'].pop('alignment')
        old['layout']['annotations']['alignment'] = {'station_top_inset': 15}
        self.assertTrue(validate_preset(old))
        self.assertNotIn('_s3d7_alignment', to_drawing_preset(old))

    def test_validation_and_no_mutation(self):
        original = copy.deepcopy(self.preset)
        to_drawing_preset(self.preset)
        self.assertEqual(original, self.preset)
        for key, value in [('curve_info_height', -1), ('station_rotation', 361), ('element_station_height', True)]:
            bad = copy.deepcopy(self.preset)
            bad['layout']['band']['alignment']['text'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_preset(bad)

    def test_curve_text_height_spacing_and_element_offsets(self):
        ip = {'curve_start_sta_m': 0, 'curve_end_sta_m': 100,
              'band_offset_mm': 6, 'curve_type': 'simplecurve',
              'direction': 'LEFT', 'ia': '20', 'radius_m': 1000,
              'tl_m': 20, 'cl_m': 40, 'stations': {'BC': 20, 'EC': 80}}
        cfg = copy.deepcopy(self.preset['layout']['band']['alignment'])
        cfg['text'].update(curve_info_height=4.5, curve_info_line_spacing=7.0,
                           element_station_height=3.5, element_station_x_offset=5.0,
                           element_station_offset=4.0)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'input.dxf'
            source.touch()
            doc = ezdxf.new()
            msp = doc.modelspace()
            with patch('alignment_band.extract_with_stations', return_value={'ips':[ip]}):
                draw_alignment_band(msp, source, 0, 100, lambda sta: sta, 0, _text, None,
                                    alignment_settings=cfg)
            curve = list(msp.query('TEXT[layer=="ALIGNMENT_IP_TEXT"]'))
            element = list(msp.query('TEXT[layer=="ALIGNMENT_ELEMENT_TEXT"]'))
            self.assertEqual(len(curve), 2)
            self.assertEqual(curve[0].dxf.height, 4.5)
            self.assertAlmostEqual(curve[0].dxf.insert.y-curve[1].dxf.insert.y, 7.0)
            self.assertEqual(element[0].dxf.height, 3.5)
            self.assertAlmostEqual(element[0].dxf.insert.x, 25.0)

if __name__ == '__main__':
    unittest.main()
