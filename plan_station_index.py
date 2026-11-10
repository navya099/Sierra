"""Exact nearest-FL segment search with AABB tree; earliest segment wins ties."""
import heapq
import math

def bbox_d2(b,x,y):
    dx=max(b[0]-x,0.,x-b[2]);dy=max(b[1]-y,0.,y-b[3]);return dx*dx+dy*dy

class FLStationIndex:
    def __init__(self,points,distances,station_origin=0.,leaf_size=12):
        if len(points)<2 or len(points)!=len(distances) or leaf_size<1:raise ValueError('Invalid FL')
        self.distances=distances;self.origin=station_origin;self.segments=[];self.leaf_size=leaf_size
        for i,(a,b) in enumerate(zip(points,points[1:])):
            dx=b[0]-a[0];dy=b[1]-a[1];length2=dx*dx+dy*dy
            if length2<1e-16:continue
            box=(min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1]))
            self.segments.append((i,a[0],a[1],dx,dy,length2,box))
        if not self.segments:raise ValueError('FL has no valid segments')
        self.root=self._build(list(range(len(self.segments))))
    def _build(self,ids):
        boxes=[self.segments[j][6] for j in ids]
        box=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
        if len(ids)<=self.leaf_size:return (box,ids,None,None)
        axis=0 if box[2]-box[0]>=box[3]-box[1] else 1
        ids.sort(key=lambda j:(self.segments[j][6][axis]+self.segments[j][6][axis+2],self.segments[j][0]))
        mid=len(ids)//2
        return (box,None,self._build(ids[:mid]),self._build(ids[mid:]))
    def project(self,point):
        x,y=point[0],point[1];best=float('inf');best_i=None;best_t=0.;seq=0
        heap=[(bbox_d2(self.root[0],x,y),seq,self.root)]
        while heap:
            lower,_,node=heapq.heappop(heap)
            if lower>best:break
            _,ids,left,right=node
            if ids is not None:
                for j in ids:
                    i,ax,ay,dx,dy,l2,_=self.segments[j]
                    t=max(0.,min(1.,((x-ax)*dx+(y-ay)*dy)/l2))
                    qx=ax+t*dx;qy=ay+t*dy;d2=(x-qx)**2+(y-qy)**2
                    if d2<best or (d2==best and (best_i is None or i<best_i)):
                        best,best_i,best_t=d2,i,t
            else:
                for child in (left,right):
                    d2=bbox_d2(child[0],x,y)
                    if d2<=best:
                        seq+=1;heapq.heappush(heap,(d2,seq,child))
        sta=self.origin+self.distances[best_i]+best_t*(self.distances[best_i+1]-self.distances[best_i])
        return sta,math.sqrt(best)
