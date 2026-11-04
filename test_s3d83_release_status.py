import copy, unittest
from profile_presets import validate_preset, load_preset, list_presets
class TestReleaseStatus(unittest.TestCase):
    def test_release_h1000(self):
        d=load_preset('cad',1000,400)
        self.assertEqual(d['status'],'RELEASE')
        self.assertEqual(d['schema_version'],2)
    def test_release_h5000(self):
        self.assertEqual(load_preset('cad',5000,1000)['status'],'RELEASE')
    def test_listing(self):
        found={(x['mode'],x['horizontal_scale'],x['vertical_scale']):x['status'] for x in list_presets()}
        self.assertEqual(found[('cad',1000,400)],'RELEASE')
    def test_old_statuses_remain_valid(self):
        d=load_preset('cad',1000,400)
        for status in ('baseline','provisional','RELEASE'):
            x=copy.deepcopy(d);x['status']=status;validate_preset(x)
    def test_invalid_status_rejected(self):
        d=load_preset('cad',1000,400)
        for status in ('release','Released','',None):
            x=copy.deepcopy(d);x['status']=status
            with self.assertRaises(ValueError):validate_preset(x)
if __name__=='__main__':unittest.main()
