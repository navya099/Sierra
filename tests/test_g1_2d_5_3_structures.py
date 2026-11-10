"""Sierra G1-2D-5-3: structure dispatch/CSV regression tests.
Place in repository root; run: python -m unittest -v test_g1_2d_5_3_structures
No production source files are modified. Geometry is mocked where indicated.
"""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from combined_plan_profile.structure_inputs_b8 import StructureSegment, load_structures
from combined_plan_profile import plan_structure_renderer_b9 as renderer


class StructureRegression(unittest.TestCase):
    def setUp(self):
        self.br = StructureSegment('BRIDGE', 100, 180, name='B1')
        self.tu = StructureSegment('TUNNEL', 300, 450, name='T1')
        self.points = [(0., 0.), (1000., 0.)]
        self.distances = [0., 1000.]
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def settings(self, config):
        p = Path(self.temp.name) / 'settings.json'
        p.write_text(json.dumps(config), encoding='utf-8')
        return p

    def cache(self, structures=None, config=None, label_style=None):
        return renderer.build_structure_cache(
            [self.br, self.tu] if structures is None else structures,
            self.points, self.distances, 0., self.settings(config or {}),
            label_style=label_style, horizontal_scale=1000.)

    def test_01_csv_bridge_tunnel_counts(self):
        path = Path(self.temp.name) / 'structures.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['kind','start_sta','end_sta','name'])
            w.writeheader()
            for i in range(10):
                w.writerow(dict(kind='BRIDGE', start_sta=i*100, end_sta=i*100+50, name=f'B{i}'))
            for i in range(9):
                w.writerow(dict(kind='TUNNEL', start_sta=1000+i*100, end_sta=1050+i*100, name=f'T{i}'))
        items = load_structures(path)
        self.assertEqual((len(items), sum(s.kind=='BRIDGE' for s in items),
                          sum(s.kind=='TUNNEL' for s in items)), (19, 10, 9))

    def test_02_csv_invalid_range_rejected(self):
        path = Path(self.temp.name) / 'invalid.csv'
        path.write_text('kind,start_sta,end_sta\nBRIDGE,200,100\n', encoding='utf-8')
        with self.assertRaises(ValueError): load_structures(path)

    def test_03_bridge_geometry_exists(self):
        doc = self.cache(structures=[self.br])
        layers = [e.dxf.layer for e in doc.modelspace()]
        self.assertIn('BRIDGE_SLAB_PLAN', layers)
        self.assertIn('BRIDGE_GIRDER_PLAN', layers)
        self.assertNotIn('TUNNEL_PLAN', layers)

    def test_04_labels_enabled(self):
        doc = self.cache(structures=[self.br], config={'plan': {'labels_enabled': True}})
        texts = [e for e in doc.modelspace().query('TEXT') if e.dxf.layer == 'STRUCTURE_LABEL_PLAN']
        self.assertEqual(len(texts), 2)
        self.assertTrue(any('B1' in e.dxf.text for e in texts))

    def test_05_labels_disabled_by_plan_settings(self):
        doc = self.cache(structures=[self.br], config={'plan': {'labels_enabled': False}})
        self.assertFalse([e for e in doc.modelspace().query('TEXT') if e.dxf.layer == 'STRUCTURE_LABEL_PLAN'])
        self.assertTrue(any(e.dxf.layer == 'BRIDGE_SLAB_PLAN' for e in doc.modelspace()))

    def test_06_labels_disabled_by_preset(self):
        style = {'enabled': False, 'text': {'height': 3., 'color': 1},
                 'placement': {'offset': 15.}, 'layer': 'STRUCTURE_LABEL_PLAN'}
        doc = self.cache(structures=[self.br], label_style=style)
        self.assertFalse([e for e in doc.modelspace().query('TEXT') if e.dxf.layer == 'STRUCTURE_LABEL_PLAN'])

    def test_07_independent_plan_style(self):
        style = {'enabled': True, 'text': {'height': 8., 'color': 3},
                 'placement': {'offset': 15.}, 'layer': 'STRUCTURE_LABEL_PLAN'}
        doc = self.cache(structures=[self.br], label_style=style)
        texts = [e for e in doc.modelspace().query('TEXT') if e.dxf.layer == 'STRUCTURE_LABEL_PLAN']
        self.assertEqual(len(texts), 2)
        self.assertTrue(all(abs(e.dxf.height - 8.) < 1e-8 for e in texts))
        self.assertEqual(doc.layers.get('STRUCTURE_LABEL_PLAN').dxf.color, 3)

    def test_08_bridge_abutment_template_dispatch(self):
        with patch.object(renderer, 'draw_plan_abutments') as abutment:
            self.cache(structures=[self.br], config={'plan': {'bridge_abutment_plan_dxf': 'sample.dxf'}})
            abutment.assert_called_once()

    def test_09_tunnel_builtin_portal_dispatch(self):
        with patch.object(renderer, 'draw_tunnel_plan') as tunnel, \
             patch.object(renderer, 'draw_plan_portals') as builtin, \
             patch.object(renderer, 'draw_custom_plan_portals') as custom:
            self.cache(structures=[self.tu])
            tunnel.assert_called_once()
            builtin.assert_called_once()
            custom.assert_not_called()

    def test_10_tunnel_custom_portal_dispatch(self):
        with patch.object(renderer, 'draw_tunnel_plan') as tunnel, \
             patch.object(renderer, 'draw_plan_portals') as builtin, \
             patch.object(renderer, 'draw_custom_plan_portals') as custom:
            self.cache(structures=[self.tu], config={'portal': {'plan_custom_dxf': 'sample.dxf'}})
            tunnel.assert_called_once()
            custom.assert_called_once()
            builtin.assert_not_called()

    def test_11_tunnel_section_template_dispatch(self):
        with patch.object(renderer, 'load_tunnel_section', return_value=None) as loader, \
             patch.object(renderer, 'draw_tunnel_plan') as tunnel, \
             patch.object(renderer, 'draw_plan_portals'):
            self.cache(structures=[self.tu], config={'tunnel': {'section_dxf': 'sample.dxf'}})
            loader.assert_called_once_with('sample.dxf')
            tunnel.assert_called_once()

    def test_12_bridge_and_tunnel_both_dispatched(self):
        with patch.object(renderer, 'draw_tunnel_plan') as tunnel, \
             patch.object(renderer, 'draw_plan_portals'):
            doc = self.cache()
            tunnel.assert_called_once()
            self.assertTrue(any(e.dxf.layer == 'BRIDGE_SLAB_PLAN' for e in doc.modelspace()))
            texts = [e for e in doc.modelspace().query('TEXT') if e.dxf.layer == 'STRUCTURE_LABEL_PLAN']
            self.assertEqual(len(texts), 4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
