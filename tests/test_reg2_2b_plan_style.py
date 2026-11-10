"""REG2-2-B regression tests; run: python -m unittest tests.test_reg2_2b_plan_style"""
import copy
import unittest
from dataclasses import FrozenInstanceError
from profile_presets.loader import load_preset
from profile_presets.plan_annotation_style import plan_style_from_preset


class PlanStyleTests(unittest.TestCase):
    def test_explicit_presets(self):
        for h, v, tick_interval, tick_length in ((1000, 400, 20, 3), (5000, 1000, 40, 15)):
            with self.subTest(h=h):
                preset = load_preset('cad', h, v)
                before = copy.deepcopy(preset)
                style = plan_style_from_preset(preset)
                self.assertEqual(preset, before)
                self.assertEqual(style.station.km.interval, 1000)
                self.assertEqual(style.station.main.interval, 200)
                self.assertEqual(style.station.tick.interval, tick_interval)
                self.assertEqual(style.station.tick.length, tick_length)
                self.assertEqual(style.vip.text.height, 3 * h / 1000)
                self.assertIsNone(style.station.km.text.color)
                with self.assertRaises(FrozenInstanceError):
                    style.station.tick.length = 999

    def test_legacy_fallback(self):
        for h, v, interval in ((1000, 400, 20), (5000, 1000, 40)):
            with self.subTest(h=h):
                preset = load_preset('cad', h, v)
                del preset['layout']['annotations']['plan']
                before = copy.deepcopy(preset)
                style = plan_style_from_preset(preset)
                self.assertEqual(style.station.tick.interval, interval)
                self.assertEqual(preset, before)

    def test_explicit_override(self):
        preset = load_preset('cad', 1000, 400)
        plan = preset['layout']['annotations']['plan']
        plan['station']['tick']['interval'] = 25
        plan['station']['km']['text']['color'] = 3
        plan['vip']['leader']['stem_length'] = 42
        style = plan_style_from_preset(preset)
        self.assertEqual(style.station.tick.interval, 25)
        self.assertEqual(style.station.km.text.color, 3)
        self.assertEqual(style.vip.leader.stem_length, 42)

    def test_invalid_explicit_not_silently_defaulted(self):
        preset = load_preset('cad', 1000, 400)
        del preset['layout']['annotations']['plan']['station']['tick']
        with self.assertRaises((ValueError, KeyError)):
            plan_style_from_preset(preset)


if __name__ == '__main__':
    unittest.main()
