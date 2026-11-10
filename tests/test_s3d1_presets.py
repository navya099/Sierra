import copy
import unittest
from profile_presets import list_presets, validate_preset
from test_preset_fixture import load_preset

class PresetTests(unittest.TestCase):
    def test_all_six(self):
        items = list_presets()
        self.assertEqual(len(items), 6)
        self.assertEqual({x['mode'] for x in items}, {'cad', 'report'})

    def test_mode_isolation(self):
        cad = load_preset('cad', 1000, 400)
        report = load_preset('report', 1000, 400)
        self.assertEqual(cad['layout'], report['layout'])
        cad['layout']['band']['ground_height'] = 99
        self.assertEqual(load_preset('cad', 1000, 400)['layout']['band']['ground_height'], 20)
        self.assertEqual(report['layout']['band']['ground_height'], 20)

    def test_baseline_dimensions(self):
        for mode in ('cad', 'report'):
            d = load_preset(mode, 1000, 400)
            self.assertEqual(sum(d['layout']['band'][k] for k in ('alignment_height','ground_height','design_height','fill_height','cut_height')), 90)
            self.assertEqual(d['layout']['profile']['plot_lower_y'], 150)
            self.assertEqual(d['layout']['profile']['plot_upper_y'], 250)

    def test_provisional_not_frozen(self):
        for mode in ('cad','report'):
            for h,v in ((5000,1000),(25000,5000)):
                self.assertEqual(load_preset(mode,h,v)['status'],'provisional')

    def test_reject_invalid(self):
        d = load_preset('cad',1000,400)
        d['layout']['text']['data_text_height'] = -1
        with self.assertRaises(ValueError): validate_preset(d)
        d = load_preset('cad',1000,400)
        d['visibility']['pier_details'] = 'false'
        with self.assertRaises(ValueError): validate_preset(d)

    def test_mismatch_and_missing(self):
        with self.assertRaises(FileNotFoundError): load_preset('cad', 7777, 3333)
        with self.assertRaises(ValueError): load_preset('wrong',1000,400)

if __name__ == '__main__': unittest.main()
