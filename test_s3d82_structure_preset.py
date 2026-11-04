import copy
import json
import unittest
from pathlib import Path
from profile_presets.loader import validate_preset
from profile_presets.runtime import to_drawing_preset
from structure_label import ProfileLabelStyle, LabelSettings, label_lines

ROOT = Path(__file__).resolve().parent

class StructurePresetTests(unittest.TestCase):
    def setUp(self):
        self.p = json.loads((ROOT/'profile_presets/cad/h5000_v1000.json').read_text(encoding='utf-8'))

    def test_roundtrip_and_immutable(self):
        before = copy.deepcopy(self.p)
        validate_preset(self.p)
        converted = to_drawing_preset(self.p)
        self.assertEqual(self.p, before)
        self.assertEqual(converted['_s3d8_structure_label'], self.p['layout']['annotations']['structure_label'])

    def test_old_preset_without_style(self):
        del self.p['layout']['annotations']['structure_label']
        validate_preset(self.p)
        self.assertEqual(ProfileLabelStyle.from_preset(to_drawing_preset(self.p).get('_s3d8_structure_label')), ProfileLabelStyle())

    def test_invalid_color(self):
        self.p['layout']['annotations']['structure_label']['text']['color'] = 256
        with self.assertRaises(ValueError): validate_preset(self.p)

    def test_invalid_leader_height(self):
        self.p['layout']['annotations']['structure_label']['leader']['vertical_height'] = 0
        with self.assertRaises(ValueError): validate_preset(self.p)

    def test_negative_station_offset(self):
        self.p['layout']['annotations']['structure_label']['text']['station_offset_factor'] = -2.0
        validate_preset(self.p)
        self.assertEqual(ProfileLabelStyle.from_preset(self.p['layout']['annotations']['structure_label']).station_offset_factor, -2.0)

    def test_label_settings_content_independent(self):
        from types import SimpleNamespace
        settings=LabelSettings(station_prefix='서기(현)', bridge_type='PSC')
        bridge=SimpleNamespace(kind='BRIDGE',name='제1교량',start_sta=1200,length=200)
        title, subtitle=label_lines(bridge,settings)
        self.assertIn('PSC',title)
        self.assertIn('서기(현)',subtitle)

if __name__ == '__main__': unittest.main()
