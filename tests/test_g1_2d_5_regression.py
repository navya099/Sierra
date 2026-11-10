"""G1-2D-5: preset compatibility and generated-DXF regression checks.
Run from Sierra repository root:
  python test_g1_2d_5_regression.py
  python test_g1_2d_5_regression.py --dxf-dir C:/Temp/G1-2D-2 --plan-height 8 --profile-height 3
Requires project dependencies only for --dxf-dir checks (ezdxf).
"""
import argparse
import copy
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from profile_presets.loader import validate_preset

PLAN = {'enabled': True, 'text': {'height': 8.0, 'color': 3},
        'placement': {'offset': 15.0}, 'layer': 'STRUCTURE_LABEL_PLAN'}


def preset(name='h1000_v400.json'):
    return json.loads((ROOT / 'profile_presets' / 'cad' / name).read_text(encoding='utf-8'))


def with_plan(data, plan=PLAN):
    result = copy.deepcopy(data)
    result['layout']['annotations']['plan_structure_label'] = copy.deepcopy(plan)
    return result


class PresetRegression(unittest.TestCase):
    def test_01_legacy_h1000(self):
        d = preset()
        d['layout']['annotations'].pop('plan_structure_label', None)
        self.assertTrue(validate_preset(d, expected_mode='cad', expected_scales=(1000, 400)))

    def test_02_legacy_h5000(self):
        d = preset('h5000_v1000.json')
        d['layout']['annotations'].pop('plan_structure_label', None)
        self.assertTrue(validate_preset(d, expected_mode='cad', expected_scales=(5000, 1000)))

    def test_03_new_plan_style(self):
        self.assertTrue(validate_preset(with_plan(preset()), expected_mode='cad', expected_scales=(1000, 400)))

    def test_04_profile_style_unchanged(self):
        original = preset()
        modified = with_plan(original)
        self.assertEqual(original['layout']['annotations']['structure_label'],
                         modified['layout']['annotations']['structure_label'])

    def test_05_disabled_plan_allowed(self):
        d = with_plan(preset())
        d['layout']['annotations']['plan_structure_label']['enabled'] = False
        self.assertTrue(validate_preset(d))

    def test_06_zero_offset_allowed(self):
        d = with_plan(preset())
        d['layout']['annotations']['plan_structure_label']['placement']['offset'] = 0
        self.assertTrue(validate_preset(d))

    def test_07_negative_offset_allowed(self):
        d = with_plan(preset())
        d['layout']['annotations']['plan_structure_label']['placement']['offset'] = -15
        self.assertTrue(validate_preset(d))

    def test_08_reject_zero_height(self):
        d = with_plan(preset())
        d['layout']['annotations']['plan_structure_label']['text']['height'] = 0
        with self.assertRaises(ValueError): validate_preset(d)

    def test_09_reject_color_256(self):
        d = with_plan(preset())
        d['layout']['annotations']['plan_structure_label']['text']['color'] = 256
        with self.assertRaises(ValueError): validate_preset(d)

    def test_10_reject_non_boolean_enabled(self):
        d = with_plan(preset())
        d['layout']['annotations']['plan_structure_label']['enabled'] = 1
        with self.assertRaises(ValueError): validate_preset(d)

    def test_11_reject_invalid_layer(self):
        d = with_plan(preset())
        d['layout']['annotations']['plan_structure_label']['layer'] = 'BAD/NAME'
        with self.assertRaises(ValueError): validate_preset(d)

    def test_12_reject_unknown_key(self):
        d = with_plan(preset())
        d['layout']['annotations']['plan_structure_label']['unknown'] = 1
        with self.assertRaises(ValueError): validate_preset(d)

    def test_13_reject_scale_mismatch(self):
        with self.assertRaises(ValueError):
            validate_preset(preset(), expected_mode='cad', expected_scales=(5000, 1000))

    def test_14_plan_style_independent(self):
        d = with_plan(preset())
        profile = d['layout']['annotations']['structure_label']['text']['height']
        d['layout']['annotations']['plan_structure_label']['text']['height'] = 11
        self.assertEqual(profile, d['layout']['annotations']['structure_label']['text']['height'])
        self.assertEqual(11, d['layout']['annotations']['plan_structure_label']['text']['height'])
        self.assertTrue(validate_preset(d))


def audit_dxf(folder, plan_height, profile_height, color, expected_sheets):
    try:
        import ezdxf
    except ImportError as exc:
        raise SystemExit('DXF 검증에는 ezdxf 설치가 필요합니다: pip install ezdxf') from exc
    paths = sorted(Path(folder).glob('종평면도(*).dxf'))
    if not paths:
        raise AssertionError(f'종평면도 DXF를 찾지 못했습니다: {folder}')
    if expected_sheets is not None and len(paths) != expected_sheets:
        raise AssertionError(f'시트 수 불일치: 실제 {len(paths)}, 기대 {expected_sheets}')
    plan_texts = []
    for path in paths:
        doc = ezdxf.readfile(path)
        for e in doc.modelspace().query('TEXT'):
            if e.dxf.layer == 'STRUCTURE_LABEL_PLAN':
                plan_texts.append((path.name, e))
    if not plan_texts:
        raise AssertionError('STRUCTURE_LABEL_PLAN TEXT가 없습니다. 구조물 시작 측점이 포함된 시트인지 확인하세요.')
    for filename, e in plan_texts:
        if not math.isclose(e.dxf.height, plan_height, rel_tol=1e-6, abs_tol=1e-5):
            raise AssertionError(f'{filename}: 평면 TEXT 높이 {e.dxf.height} != {plan_height}')
        if color is not None:
            # BYLAYER(256) is valid; inspect effective layer color in that case.
            entity_color = e.dxf.get('color', 256)
            actual = entity_color if entity_color != 256 else e.doc.layers.get(e.dxf.layer).dxf.color
            if actual != color:
                raise AssertionError(f'{filename}: 평면 TEXT 색상 {actual} != {color}')
    print(f'[PASS] DXF {len(paths)}개, 평면 구조물 TEXT {len(plan_texts)}개: 높이={plan_height}, 색상={color}')
    if profile_height is not None:
        print('[MANUAL] 종단 TEXT 높이는 도면별 레이어/엔티티 식별 규칙 확인 후 검사하세요. '
              f'기대 높이={profile_height}. 임의 레이어 추정으로 합격 처리하지 않습니다.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dxf-dir', type=Path)
    p.add_argument('--plan-height', type=float, default=8)
    p.add_argument('--profile-height', type=float, default=3)
    p.add_argument('--plan-color', type=int, default=None)
    p.add_argument('--expected-sheets', type=int, default=None)
    args = p.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(PresetRegression))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.dxf_dir:
        audit_dxf(args.dxf_dir, args.plan_height, args.profile_height,
                  args.plan_color, args.expected_sheets)


if __name__ == '__main__':
    main()
