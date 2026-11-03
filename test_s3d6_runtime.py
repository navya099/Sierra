"""S3-D6: v2 translation and real DXF equality to the frozen v1 layout."""
import copy
import json
import unittest
from pathlib import Path
from profile_presets.loader import load_preset, validate_preset
from profile_presets.runtime import to_drawing_preset
from profile_drawing import DrawingOptions, create_profile_drawing
from test_s3d2_preset_dxf import TestS3D2, entities

ROOT = Path(__file__).resolve().parent

class RuntimeV2Tests(unittest.TestCase):
    def setUp(self):
        self.v2 = json.loads((ROOT / 'h5000_v1000_schema_v2.json').read_text(encoding='utf-8'))
        self.v1 = load_preset('cad', 5000, 1000)

    def test_legacy_no_mutation(self):
        self.assertEqual(to_drawing_preset(self.v1), self.v1)
        self.assertIsNot(to_drawing_preset(self.v1), self.v1)

    def test_nested_mapping_and_no_mutation(self):
        original = copy.deepcopy(self.v2)
        p = to_drawing_preset(self.v2)
        self.assertEqual(original, self.v2)
        self.assertTrue(validate_preset(p))
        self.assertEqual(p['layout']['band']['distance_rule_offset'], 70)
        self.assertEqual(p['layout']['band']['grade_rule_offset'], 140)
        self.assertEqual(p['layout']['absolute_dimensions']['profile']['reserved_structure_depth'], 250)
        self.assertEqual(p['layout']['annotations']['vip_elevation_text_height'], 15)
        self.assertEqual(p['layout']['annotations']['grade_text_height'], 50)

    def test_v2_dxf_same_as_v1_for_same_visibility(self):
        # v2 draft visibility differs from the user's frozen third revision;
        # compare equivalent visibility policies to isolate layout migration.
        self.v2['visibility'] = copy.deepcopy(self.v1['visibility'])
        self.v2['visibility_policy'] = copy.deepcopy(self.v1['visibility_policy'])
        fixture = TestS3D2('test_baseline_exact')
        fixture.setUp()
        try:
            a, b = fixture.root / 'v1.dxf', fixture.root / 'v2.dxf'
            def options(p):
                return DrawingOptions(drawing_mode='cad', horizontal_scale=5000,
                                      vertical_scale=1000, layout_preset=p)
            ra = create_profile_drawing(fixture.src, a, options(self.v1))
            rb = create_profile_drawing(fixture.src, b, options(self.v2))
            self.assertEqual(ra['plot_lower_y'], rb['plot_lower_y'])
            self.assertEqual(ra['plot_upper_y'], rb['plot_upper_y'])
            self.assertEqual(entities(a), entities(b))
        finally:
            fixture.tearDown()

if __name__ == '__main__':
    unittest.main()
