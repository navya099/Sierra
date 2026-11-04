"""S3-D9: external custom preset and built-in RELEASE regression."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from profile_presets.loader import load_preset_file, load_preset, list_presets

ROOT = Path(__file__).resolve().parent
CUSTOM = ROOT / 'custom_preset.json'

class CustomPresetReleaseTests(unittest.TestCase):
    def test_external_custom_scale(self):
        data = load_preset_file(CUSTOM, expected_mode='cad', expected_scales=(600, 100))
        self.assertEqual((data['schema_version'], data['status']), (2, 'RELEASE'))
        self.assertEqual(data['layout']['annotations']['structure_label']['text']['height'], 3)

    def test_reject_wrong_mode_and_scale(self):
        with self.assertRaises(ValueError):
            load_preset_file(CUSTOM, expected_mode='report')
        with self.assertRaises(ValueError):
            load_preset_file(CUSTOM, expected_scales=(1000, 400))

    def test_reject_invalid_status_and_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'custom.json'
            data = load_preset_file(CUSTOM)
            data['status'] = 'release'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(ValueError): load_preset_file(path)
            data['status'] = 'RELEASE'
            data['layout']['band']['text']['data_height'] = -2
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(ValueError): load_preset_file(path)

    def test_external_bom_and_caller_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'any_name.json'
            path.write_text(CUSTOM.read_text(encoding='utf-8'), encoding='utf-8-sig')
            a = load_preset_file(path)
            a['layout']['band']['text']['data_height'] = 999
            b = load_preset_file(path)
            self.assertEqual(b['layout']['band']['text']['data_height'], 20)

    def test_builtins_unchanged(self):
        self.assertEqual(load_preset('cad', 1000, 400)['status'], 'RELEASE')
        self.assertEqual(load_preset('cad', 5000, 1000)['status'], 'RELEASE')
        self.assertEqual(len(list_presets()), 6)

if __name__ == '__main__': unittest.main()
