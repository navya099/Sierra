"""S3-B integration smoke tests: actual DXF, CAD metre coordinates, and legacy report."""
import tempfile
import unittest
from pathlib import Path
import ezdxf
from profile_drawing import DrawingOptions, create_profile_drawing
from profile_transform import DrawingMode

class TestS3BDXF(unittest.TestCase):
    def test_cad_and_report(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); src=p/'source.dxf'
            doc=ezdxf.new('R2010')
            doc.modelspace().add_lwpolyline([(0,100),(350,105),(700,100)],dxfattribs={'layer':'PLAN_PROFILE'})
            doc.modelspace().add_lwpolyline([(0,103),(350,107),(700,103)],dxfattribs={'layer':'GROUND_PROFILE'})
            doc.saveas(src)
            for mode,h,v,expected_dx,expected_dy,units in [
                (DrawingMode.CAD,1000,400,700,12.5,6),
                (DrawingMode.CAD,5000,1000,700,25,6),
                (DrawingMode.REPORT,1000,400,700,12.5,4),
                (DrawingMode.REPORT,5000,1000,140,5,4),
            ]:
                out=p/f'{mode.value}_{h}.dxf'
                result=create_profile_drawing(src,out,DrawingOptions(drawing_mode=mode,horizontal_scale=h,vertical_scale=v,auto_datum=False,graph_bottom=90))
                saved=ezdxf.readfile(out)
                self.assertEqual(saved.header['$INSUNITS'],units)
                line=next(e for e in saved.modelspace().query('LWPOLYLINE') if e.dxf.layer=='PLAN_PROFILE')
                xy=list(line.get_points('xy'))
                self.assertAlmostEqual(xy[-1][0]-xy[0][0],expected_dx)
                self.assertAlmostEqual(xy[1][1]-xy[0][1],expected_dy)
                self.assertEqual(result['drawing_mode'],mode.value)
    def test_exaggeration_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);src=p/'s.dxf';doc=ezdxf.new('R2010');m=doc.modelspace()
            m.add_lwpolyline([(0,100),(100,120)],dxfattribs={'layer':'PLAN_PROFILE'})
            m.add_lwpolyline([(0,105),(100,125)],dxfattribs={'layer':'GROUND_PROFILE'})
            doc.saveas(src)
            for mode,expected in [(DrawingMode.CAD,20),(DrawingMode.REPORT,4)]:
                dst=p/f'{mode.value}.dxf'
                create_profile_drawing(src,dst,DrawingOptions(drawing_mode=mode,horizontal_scale=5000,vertical_scale=1000,vertical_exaggeration_enabled=False,auto_datum=False,graph_bottom=90))
                e=next(e for e in ezdxf.readfile(dst).modelspace().query('LWPOLYLINE') if e.dxf.layer=='PLAN_PROFILE')
                pts=list(e.get_points('xy'))
                self.assertAlmostEqual(pts[-1][1]-pts[0][1],expected)
if __name__=='__main__':unittest.main()
