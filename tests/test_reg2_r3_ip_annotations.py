import copy
import unittest

import ezdxf

from profile_presets.loader import load_preset, validate_preset
from profile_presets.plan_annotation_style import plan_style_from_preset
from combined_plan_profile.plan_ip_labels_v1_8b import render_ip_labels


IP_TEXT = "IP\uBB38\uC790"
IP_TABLE = "IP\uC81C\uC6D0\uD45C"


def make_ip_preset():
    preset = copy.deepcopy(load_preset("cad", 1000, 400))
    preset["layout"]["annotations"]["plan"]["ip"] = {
        "enabled": True,
        "text": {"height": 8.0, "color": 3},
        "table": {"text_height": 6.0, "color": 5},
    }
    return preset


def make_source():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    for name in (IP_TEXT, IP_TABLE):
        if name not in doc.layers:
            doc.layers.new(name)

    msp.add_text(
        "IP1",
        dxfattribs={
            "layer": IP_TEXT,
            "height": 3.0,
            "color": 1,
            "insert": (100, 400),
        },
    )

    block = doc.blocks.new("IP_Block_Test")
    block.add_text(
        "TABLE",
        dxfattribs={
            "layer": IP_TABLE,
            "height": 3.0,
            "color": 7,
            "insert": (120, 420),
        },
    )

    msp.add_blockref("IP_Block_Test", (0, 0))
    return doc


def render(source, *, ip_style=None, rect=None, scale=1000):
    target = ezdxf.new("R2010")

    result = render_ip_labels(
        source,
        target,
        lambda p: (p[0], p[1]),
        0.0,
        scale,
        ip_style=ip_style,
        plan_rect=rect,
    )

    return target, result


class TestReg2R3IpAnnotations(unittest.TestCase):

    def test_explicit_preset_style(self):
        preset = make_ip_preset()
        validate_preset(preset)
        style = plan_style_from_preset(preset).ip

        target, counts = render(
            make_source(),
            ip_style=style,
            rect=(0, 0, 1000, 1000),
        )

        self.assertEqual(counts["ip_text_drawn"], 1)
        self.assertEqual(counts["ip_table_drawn"], 1)

        texts = {
            e.dxf.text: e
            for e in target.modelspace().query("TEXT")
        }

        self.assertEqual(texts["IP1"].dxf.height, 8.0)
        self.assertEqual(texts["IP1"].dxf.color, 3)
        self.assertEqual(texts["TABLE"].dxf.height, 6.0)
        self.assertEqual(texts["TABLE"].dxf.color, 5)

    def test_legacy_style_preserved(self):
        target, counts = render(
            make_source(),
            rect=(0, 0, 1000, 1000),
            scale=5000,
        )

        self.assertEqual(counts["ip_text_drawn"], 1)
        self.assertEqual(counts["ip_table_drawn"], 1)

        texts = {
            e.dxf.text: e
            for e in target.modelspace().query("TEXT")
        }

        self.assertAlmostEqual(texts["IP1"].dxf.height, 0.6)
        self.assertEqual(texts["IP1"].dxf.color, 1)
        self.assertAlmostEqual(texts["TABLE"].dxf.height, 0.6)
        self.assertEqual(texts["TABLE"].dxf.color, 7)

    def test_scaled_clipping(self):
        source = make_source()

        _, small = render(
            source,
            rect=(0, 0, 50, 50),
        )

        _, large = render(
            source,
            rect=(0, 0, 1000, 1000),
        )

        self.assertEqual(small["ip_text_drawn"], 0)
        self.assertEqual(small["ip_table_drawn"], 0)
        self.assertEqual(large["ip_text_drawn"], 1)
        self.assertEqual(large["ip_table_drawn"], 1)

    def test_disabled_ip(self):
        preset = make_ip_preset()
        preset["layout"]["annotations"]["plan"]["ip"]["enabled"] = False

        style = plan_style_from_preset(preset).ip

        target, counts = render(
            make_source(),
            ip_style=style,
            rect=(0, 0, 1000, 1000),
        )

        self.assertEqual(len(target.modelspace()), 0)
        self.assertEqual(sum(counts.values()), 0)

    def test_invalid_ip_color(self):
        preset = make_ip_preset()
        preset["layout"]["annotations"]["plan"]["ip"]["text"]["color"] = 256

        with self.assertRaises(ValueError):
            validate_preset(preset)

    def test_invalid_ip_height(self):
        preset = make_ip_preset()
        preset["layout"]["annotations"]["plan"]["ip"]["text"]["height"] = 0

        with self.assertRaises(ValueError):
            validate_preset(preset)

    def test_h1000_saved_dxf_preserves_ip_geometry(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import math
        import re

        preset = copy.deepcopy(load_preset("cad", 1000, 400))
        preset["layout"]["annotations"]["plan"]["ip"] = {
            "enabled": True,
            "text": {"height": 3.0, "color": 1},
            "table": {"text_height": 3.0, "color": 7},
        }

        validate_preset(preset)
        ip_style = plan_style_from_preset(preset).ip
        source = make_source()

        target, counts = render(
            source,
            ip_style=ip_style,
            rect=(70, 330, 770, 530),
        )

        self.assertEqual(counts["ip_text_drawn"], 1)
        self.assertEqual(counts["ip_table_drawn"], 1)

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ip_h1000.dxf"
            target.saveas(path)

            saved = ezdxf.readfile(path)

            def normalize(name):
                return re.sub(
                    r"\\U\+([0-9A-Fa-f]{4})",
                    lambda m: chr(int(m.group(1), 16)),
                    name,
                    flags=re.IGNORECASE,
                )

            texts = list(saved.modelspace().query("TEXT"))

            ip_texts = [
                e for e in texts
                if normalize(e.dxf.layer) == IP_TEXT
            ]
            table_texts = [
                e for e in texts
                if normalize(e.dxf.layer) == IP_TABLE
            ]

            self.assertEqual(len(ip_texts), 1)
            self.assertEqual(len(table_texts), 1)

            self.assertAlmostEqual(ip_texts[0].dxf.height, 3.0)
            self.assertEqual(ip_texts[0].dxf.color, 1)
            self.assertAlmostEqual(table_texts[0].dxf.height, 3.0)
            self.assertEqual(table_texts[0].dxf.color, 7)

            self.assertAlmostEqual(ip_texts[0].dxf.insert.x, 100)
            self.assertAlmostEqual(ip_texts[0].dxf.insert.y, 400)
            self.assertAlmostEqual(table_texts[0].dxf.insert.x, 120)
            self.assertAlmostEqual(table_texts[0].dxf.insert.y, 420)

if __name__ == "__main__":
    unittest.main()
