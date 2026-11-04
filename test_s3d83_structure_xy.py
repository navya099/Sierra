import copy
import json
import math
import unittest
from pathlib import Path
import ezdxf
from types import SimpleNamespace
from structure_label import LabelSettings, ProfileLabelStyle, draw_structure_labels
from profile_presets.loader import validate_preset

ROOT=Path(__file__).resolve().parent
class XYTests(unittest.TestCase):
    def setUp(self):
        self.p=json.loads((ROOT/'profile_presets/cad/h5000_v1000.json').read_text(encoding='utf-8'))
        self.cfg=self.p['layout']['annotations']['structure_label']
    def test_valid(self):
        validate_preset(self.p)
        self.assertIsNotNone(ProfileLabelStyle.from_preset(self.cfg).title_xy)
    def test_invalid(self):
        for value in ('nan', None, True):
            q=copy.deepcopy(self.p)
            q['layout']['annotations']['structure_label']['text']['title']['x_offset']=value
            with self.assertRaises(ValueError):validate_preset(q)
    def test_legacy(self):
        q=copy.deepcopy(self.p)
        del q['layout']['annotations']['structure_label']['text']['title']
        del q['layout']['annotations']['structure_label']['text']['station']
        validate_preset(q)
        self.assertIsNone(ProfileLabelStyle.from_preset(q['layout']['annotations']['structure_label']).title_xy)
    def test_placement_and_leader_unchanged(self):
        doc=ezdxf.new();doc.styles.new('KOREAN',dxfattribs={'font':'txt'})
        msp=doc.modelspace()
        structure=SimpleNamespace(kind='BRIDGE',name='A',start_sta=100,length=30)
        seg=SimpleNamespace(start_sta=0,end_sta=200,datum_el=0)
        cfg=copy.deepcopy(self.cfg)
        cfg['text']['title']={'x_offset':12,'y_offset':-8}
        cfg['text']['station']={'x_offset':-7,'y_offset':9}
        style=ProfileLabelStyle.from_preset(cfg)
        count=draw_structure_labels(msp,[structure],LabelSettings(),0,200,[seg],lambda sta:50,lambda sta:sta,lambda el,datum:el,style=style)
        self.assertEqual(count,1)
        lines=list(msp.query('LINE'));texts=list(msp.query('TEXT'))
        self.assertEqual(len(lines),2);self.assertEqual(len(texts),2)
        self.assertAlmostEqual(lines[0].dxf.end.x,100)
        self.assertAlmostEqual(lines[0].dxf.end.y,50+style.vertical_height)
        self.assertAlmostEqual(texts[0].dxf.insert.x,112)
        self.assertAlmostEqual(texts[0].dxf.insert.y,50+style.vertical_height-8)
        self.assertAlmostEqual(texts[1].dxf.insert.x,93)
        self.assertAlmostEqual(texts[1].dxf.insert.y,50+style.vertical_height+9)
    def test_conversion_preserves_old_coordinates(self):
        style=ProfileLabelStyle.from_preset(self.cfg)
        theta=math.radians(style.leader_angle)
        for xy,factor in ((style.title_xy,style.title_offset_factor),(style.station_xy,style.station_offset_factor)):
            off=style.text_height*factor
            self.assertAlmostEqual(xy[0],-math.sin(theta)*off)
            self.assertAlmostEqual(xy[1],math.cos(theta)*off)
if __name__=='__main__':unittest.main()
