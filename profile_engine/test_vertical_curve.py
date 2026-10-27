import unittest
from vertical_curve import VerticalAlignment

class VerticalCurveTests(unittest.TestCase):
    def setUp(self):
        self.a = VerticalAlignment([(0,100),(1000,110),(2000,100)], {1:200})
    def test_boundaries_and_midpoint(self):
        self.assertAlmostEqual(self.a.evaluate(900)[0],109)
        self.assertAlmostEqual(self.a.evaluate(1100)[0],109)
        self.assertAlmostEqual(self.a.evaluate(1000)[0],109.5)
        self.assertAlmostEqual(self.a.evaluate(1000)[1],0)
        self.assertAlmostEqual(self.a.curves[0].extremum()[0],1000)
    def test_continuity(self):
        for s in (900,1100):
            a,b=self.a.evaluate(s-0.00001),self.a.evaluate(s+0.00001)
            self.assertLess(abs(a[0]-b[0]),0.000001)
            self.assertLess(abs(a[1]-b[1]),0.00001)
    def test_valley(self):
        a=VerticalAlignment([(0,110),(1000,100),(2000,110)],{1:200})
        self.assertAlmostEqual(a.evaluate(1000)[0],100.5)
    def test_zero_length_is_tangent(self):
        a=VerticalAlignment([(0,100),(1000,110),(2000,100)])
        self.assertAlmostEqual(a.evaluate(1000)[0],110)
    def test_ordinate_symmetric_and_endpoints(self):
        c = self.a.curves[0]
        for station, expected in ((900, 0), (950, -0.125), (1000, -0.5),
                                  (1050, -0.125), (1100, 0)):
            self.assertAlmostEqual(c.ordinate(station), expected)
        with self.assertRaises(ValueError):
            c.ordinate(899)

    def test_ordinate_valley(self):
        a = VerticalAlignment([(0,110),(1000,100),(2000,110)],{1:200})
        c = a.curves[0]
        self.assertAlmostEqual(c.ordinate(1000), 0.5)
        self.assertAlmostEqual(c.ordinate(1050), 0.125)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            VerticalAlignment([(0,100),(1000,110),(2000,100)],{1:2100})
        with self.assertRaises(ValueError):
            VerticalAlignment([(0,100),(1000,110),(2000,100)],{0:200})
        with self.assertRaises(ValueError):
            self.a.evaluate(-1)

if __name__=='__main__': unittest.main()
