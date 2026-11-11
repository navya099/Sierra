import unittest

import ezdxf

from combined_plan_profile.plan_structure_renderer_b9 import (
    render_structure_sheet,
)


class TestREG2R2BPlanStructureClipping(unittest.TestCase):

    @staticmethod
    def make_source(text_y):
        doc = ezdxf.new("R2013")
        doc.layers.new("STRUCTURE_LABEL_PLAN", dxfattribs={"color": 3})
        doc.modelspace().add_text(
            "T. TEST",
            dxfattribs={
                "layer": "STRUCTURE_LABEL_PLAN",
                "height": 25,
                "insert": (1500, text_y),
            },
        )
        return doc

    @staticmethod
    def make_alignment(y):
        # Straight horizontal alignment, STA 0~3500
        points = [(350, y), (3850, y)]
        distances = [0.0, 3500.0]
        return points, distances

    @staticmethod
    def identity_transform(point):
        return point

    def render(self, source, points, distances, rect):
        target = ezdxf.new("R2013")

        result = render_structure_sheet(
            target,
            source,
            self.identity_transform,
            0.0,
            3500.0,
            0.0,
            points,
            distances,
            plan_rect=rect,
        )

        texts = [
            e for e in target.modelspace().query("TEXT")
            if e.dxf.layer == "STRUCTURE_LABEL_PLAN"
        ]

        return target, result, texts

    def test_h5000_plan_structure_clipping(self):
        source = self.make_source(2180)
        points, distances = self.make_alignment(2150)

        target, result, texts = self.render(
            source,
            points,
            distances,
            (350, 1650, 3850, 2650),
        )

        self.assertEqual(result["text"], 1)
        self.assertEqual(len(texts), 1)
        self.assertAlmostEqual(texts[0].dxf.height, 25.0)
        self.assertEqual(
            target.layers.get("STRUCTURE_LABEL_PLAN").dxf.color,
            3,
        )

    def test_h1000_plan_structure_clipping(self):
        source = ezdxf.new("R2013")
        source.layers.new(
            "STRUCTURE_LABEL_PLAN",
            dxfattribs={"color": 1},
        )
        source.modelspace().add_text(
            "T. TEST",
            dxfattribs={
                "layer": "STRUCTURE_LABEL_PLAN",
                "height": 3,
                "insert": (350, 430),
            },
        )

        points = [(70, 430), (770, 430)]
        distances = [0.0, 700.0]

        target, result, texts = self.render(
            source,
            points,
            distances,
            (70, 330, 770, 530),
        )

        self.assertEqual(result["text"], 1)
        self.assertEqual(len(texts), 1)
        self.assertAlmostEqual(texts[0].dxf.height, 3.0)

    def test_outside_plan_structure_clipping(self):
        source = self.make_source(3000)
        points, distances = self.make_alignment(2150)

        target, result, texts = self.render(
            source,
            points,
            distances,
            (350, 1650, 3850, 2650),
        )

        self.assertEqual(result["text"], 0)
        self.assertEqual(len(texts), 0)


if __name__ == "__main__":
    unittest.main()
