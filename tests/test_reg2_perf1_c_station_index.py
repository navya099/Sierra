import math,random,unittest
from plan_station_index import FLStationIndex
from combined_plan_profile.plan_entities_v1_7 import _station_of_point

def check(test,pts,queries):
    ds=[0.]
    for a,b in zip(pts,pts[1:]):ds.append(ds[-1]+math.dist(a,b))
    index=FLStationIndex(pts,ds,100.)
    for q in queries:
        expected=_station_of_point(q,pts,ds,100.)
        actual=index.project(q)
        test.assertAlmostEqual(actual[0],expected[0],places=8,msg=str(q))
        test.assertAlmostEqual(actual[1],expected[1],places=8,msg=str(q))

class Parity(unittest.TestCase):
    def test_corners(self):check(self,[(0,0),(10,0),(10,10)],[(0,0),(5,2),(10,10),(30,30)])
    def test_crossing(self):check(self,[(-10,-10),(10,10),(-10,10),(10,-10)],[(0,0),(1,0),(0,1),(5,5)])
    def test_ties(self):check(self,[(0,0),(10,0),(10,2),(0,2)],[(5,1),(0,1),(10,1)])
    def test_random(self):
        r=random.Random(20261110)
        for n in (3,15,100,500):
            pts=[(0.,0.)]
            for _ in range(n):
                a=r.random()*math.tau;pts.append((pts[-1][0]+10*math.cos(a),pts[-1][1]+10*math.sin(a)))
            check(self,pts,[(r.uniform(-100,100),r.uniform(-100,100)) for _ in range(250)])
    def test_duplicate(self):check(self,[(0,0),(10,0),(10,0),(20,0)],[(10,0),(15,1)])
    def test_invalid(self):
        with self.assertRaises(ValueError):FLStationIndex([(0,0)],[0])
