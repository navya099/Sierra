"""Run in Sierra root with: python -m unittest test_s3d6_loader.py"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from profile_presets.loader import load_preset, validate_preset

HERE = Path(__file__).resolve().parent.parent
V2 = HERE / 'h5000_v1000_schema_v2.json'

class TestS3D6Loader(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(V2.read_text(encoding='utf-8'))

    def test_v2_valid(self):
        self.assertTrue(validate_preset(self.data, 'cad', (5000,1000)))

    def test_v2_invalid_missing_key(self):
        obj=copy.deepcopy(self.data)
        del obj['layout']['band']['height']['alignment']
        with self.assertRaises(ValueError): validate_preset(obj)

    def test_v2_invalid_boolean_number(self):
        obj=copy.deepcopy(self.data)
        obj['layout']['band']['height']['alignment']=True
        with self.assertRaises(ValueError): validate_preset(obj)

    def test_v2_invalid_clearance_boolean(self):
        obj=copy.deepcopy(self.data)
        obj['layout']['profile']['clearance']['use_placement_clearance']=1
        with self.assertRaises(ValueError): validate_preset(obj)

    def test_v2_load_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'cad'
            dest.mkdir()
            (dest/'h5000_v1000.json').write_text(json.dumps(self.data),encoding='utf-8')
            a=load_preset('cad',5000,1000,root=temp)
            a['layout']['band']['height']['alignment']=999
            b=load_preset('cad',5000,1000,root=temp)
            self.assertEqual(b['layout']['band']['height']['alignment'],80)

if __name__ == '__main__': unittest.main()
