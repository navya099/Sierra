
import unittest

import ezdxf

from combined_plan_profile.plan_vip_annotations import (
    draw_symbol,
    render_plan_vips,
)
from profile_presets.loader import load_preset
from profile_presets.plan_annotation_style import plan_style_from_preset


class TestREG2R2APlanVIP(unittest.TestCase):

    def test_01_preset_values(self):
        for h, v, height, stem, arm in (
            (1000, 400, 3.0, 30.0, 10.5),
            (5000, 1000, 15.0, 150.0, 52.5),
        ):
            with self.subTest(scale=h):
                preset = load_preset("cad", h, v)
                vip = plan_style_from_preset(preset).vip

                self.assertTrue(vip.enabled)
                self.assertEqual(vip.text.height, height)
                self.assertEqual(vip.leader.stem_length, stem)
                self.assertEqual(vip.leader.arm_length, arm)

    def test_02_dxf_text_height_and_color(self):
        doc = ezdxf.new("R2013")
        msp = doc.modelspace()

        draw_symbol(
            msp,
            xy=(100, 400),
            tangent=(1, 0),
            grade_in=10,
            grade_out=-10,
            stem=30,
            arm=10.5,
            text_height=8,
            text_color=3,
            leader_color=5,
            plan_rect=(0, 0, 1000, 1000),
        )

        texts = list(msp.query("TEXT"))
        lines = list(msp.query("LINE"))

        self.assertEqual(len(texts), 2)
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(t.dxf.height == 8 for t in texts))
        self.assertTrue(all(t.dxf.color == 3 for t in texts))
        self.assertTrue(all(line.dxf.color == 5 for line in lines))

    def test_03_vip_disabled(self):
        doc = ezdxf.new("R2013")

        count = render_plan_vips(
            doc,
            [],
            lambda p: p,
            sheet_start=0,
            sheet_end=700,
            fl_points=[(0, 0), (700, 0)],
            fl_distances=[0, 700],
            enabled=False,
        )

        self.assertEqual(count, 0)
        self.assertEqual(len(doc.modelspace()), 0)


if __name__ == "__main__":
    unittest.main()
