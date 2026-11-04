"""S3-D2: DXF entity-level regression and preset isolation."""
import tempfile
import unittest
from pathlib import Path
import ezdxf
from profile_drawing import DrawingOptions, create_profile_drawing, options_with_preset
from profile_transform import DrawingMode
from test_preset_fixture import load_preset

def entities(path):
    doc=ezdxf.readfile(path)
    return [(e.dxftype(),e.dxf.layer,e.dxfattribs().get('text'),
             tuple(tuple(p[:2]) for p in e.get_points('xy')) if e.dxftype()=='LWPOLYLINE' else
             tuple(e.dxf.start) + tuple(e.dxf.end) if e.dxftype()=='LINE' else
             tuple(e.dxf.insert) if e.dxftype()=='TEXT' else tuple(e.dxf.center) + (e.dxf.radius,) if e.dxftype()=='CIRCLE' else None)
            for e in doc.modelspace()]

class TestS3D2(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.src=self.root/'src.dxf'
        doc=ezdxf.new('R2010');m=doc.modelspace()
        m.add_lwpolyline([(0,100),(350,105),(700,100)],dxfattribs={'layer':'PLAN_PROFILE'})
        m.add_lwpolyline([(0,103),(350,107),(700,103)],dxfattribs={'layer':'GROUND_PROFILE'})
        doc.saveas(self.src)
    def test_baseline_exact(self):
        for mode in (DrawingMode.CAD,DrawingMode.REPORT):
            for auto in (True,False):
                with self.subTest(mode=mode,auto=auto):
                    kw=dict(drawing_mode=mode,horizontal_scale=1000,vertical_scale=400,auto_datum=auto)
                    if not auto:kw['graph_bottom']=90
                    opt=DrawingOptions(**kw)
                    a=self.root/'a.dxf';b=self.root/'b.dxf'
                    create_profile_drawing(self.src,a,opt)
                    create_profile_drawing(self.src,b,options_with_preset(opt))
                    self.assertEqual(entities(a),entities(b))
    def test_mode_mismatch_rejected(self):
        opt=DrawingOptions(drawing_mode=DrawingMode.CAD,layout_preset=load_preset('report',1000,400))
        with self.assertRaises(ValueError):create_profile_drawing(self.src,self.root/'bad.dxf',opt)
    def test_preset_dimensions_applied(self):
        p=load_preset('cad',1000,400)
        p['layout']['band']['alignment_height']=30
        out=self.root/'changed.dxf'
        create_profile_drawing(self.src,out,DrawingOptions(drawing_mode=DrawingMode.CAD,layout_preset=p,auto_datum=False,graph_bottom=90))
        band=[e for e in ezdxf.readfile(out).modelspace().query('LINE') if e.dxf.layer=='PROFILE_BAND' and abs(e.dxf.start.y-e.dxf.end.y)<1e-8]
        self.assertTrue(any(abs(e.dxf.start.y-30)<1e-8 for e in band))
