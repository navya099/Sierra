"""종평면도 v1.2: 외부 도곽 + 원본 FL 데이터로 PLAN 직접 작성.
기존 final_plan / final_result 파일은 읽거나 수정하지 않는다.
원본 평면선형 DXF의 FL 레이어에서 중심선만 읽고 신규 DXF에 직접 생성한다.
"""
from pathlib import Path
import argparse
import math
import ezdxf

DRAWING_AREAS = {
    "PLAN": (35., 330., 811., 530.),
    "PROFILE": (35., 70., 811., 315.),
}

def clip_segment(a, b, rect):
    """Liang-Barsky segment clipping."""
    xmin, ymin, xmax, ymax = rect
    dx, dy = b[0]-a[0], b[1]-a[1]
    p = (-dx, dx, -dy, dy)
    q = (a[0]-xmin, xmax-a[0], a[1]-ymin, ymax-a[1])
    t0, t1 = 0., 1.
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-12:
            if qi < 0: return None
            continue
        t = qi / pi
        if pi < 0: t0 = max(t0, t)
        else: t1 = min(t1, t)
        if t0 > t1: return None
    return ((a[0]+t0*dx, a[1]+t0*dy), (a[0]+t1*dx, a[1]+t1*dy))

def read_fl(plan_source):
    src = ezdxf.readfile(str(plan_source))
    matches = [e for e in src.modelspace().query("LWPOLYLINE") if e.dxf.layer.casefold() == "fl"]
    if len(matches) != 1:
        raise ValueError(f"FL 레이어의 LWPOLYLINE이 정확히 1개여야 합니다 (현재 {len(matches)}개)")
    ent = matches[0]
    if ent.closed or any(abs(b)>1e-12 for _,_,b in ent.get_points("xyb")):
        raise ValueError("FL은 닫히지 않은 직선 세그먼트 LWPOLYLINE이어야 합니다.")
    points = [(float(x),float(y)) for x,y in ent.get_points("xy")]
    if len(points)<2: raise ValueError("FL 정점이 2개 미만입니다.")
    return points

def fit_transform(points, rect, padding=8.):
    """v1.2 위치 검증 전용 자동 맞춤. 최종 측점·축척 고정 배치는 후속 버전."""
    xmin,ymin,xmax,ymax = rect
    xs,ys=zip(*points)
    cx,cy=(min(xs)+max(xs))/2,(min(ys)+max(ys))/2
    w,h=max(xs)-min(xs),max(ys)-min(ys)
    if w<1e-9 and h<1e-9: raise ValueError("FL 길이가 0입니다.")
    scale=min((xmax-xmin-2*padding)/max(w,1e-9),
              (ymax-ymin-2*padding)/max(h,1e-9))
    tx,ty=(xmin+xmax)/2,(ymin+ymax)/2
    return [(tx+(x-cx)*scale,ty+(y-cy)*scale) for x,y in points],scale

def build(template, output, plan_source=None, show_guides=True):
    doc=ezdxf.readfile(str(template))
    msp=doc.modelspace()
    doc.header["$INSUNITS"]=4
    for name,color in (("ZPP_PLAN_AREA",3),("ZPP_PROFILE_AREA",5),
                       ("ZPP_GUIDE_LABEL",7),("ZPP_PLAN_CENTER",1)):
        if name not in doc.layers: doc.layers.new(name,dxfattribs={"color":color})
    if show_guides:
        for name,(xmin,ymin,xmax,ymax) in DRAWING_AREAS.items():
            layer="ZPP_PLAN_AREA" if name=="PLAN" else "ZPP_PROFILE_AREA"
            msp.add_lwpolyline([(xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax)],
                               close=True,dxfattribs={"layer":layer})
            msp.add_text(f"{name}_RECT ({xmin:g},{ymin:g})-({xmax:g},{ymax:g})",
                         dxfattribs={"height":5,"insert":(xmin+6,ymax-11),
                                     "layer":"ZPP_GUIDE_LABEL"})
    if plan_source is not None:
        pts,scale=fit_transform(read_fl(plan_source),DRAWING_AREAS["PLAN"])
        for a,b in zip(pts,pts[1:]):
            clipped=clip_segment(a,b,DRAWING_AREAS["PLAN"])
            if clipped and math.dist(*clipped)>1e-8:
                msp.add_line(*clipped,dxfattribs={"layer":"ZPP_PLAN_CENTER"})
        print(f"FL 중심선 직접 생성 완료 (시험용 자동맞춤 계수: {scale:.8f})")
    else:
        print("평면선형 입력 없음: 도곽·영역만 생성합니다.")
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    doc.saveas(str(output))
    return output

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--template",type=Path,default=Path(__file__).with_name("도각.dxf"))
    parser.add_argument("--output",type=Path,default=Path(__file__).with_name("종평면도(1).dxf"))
    parser.add_argument("--plan-source",type=Path,default=None,help="FL 레이어가 있는 원본 평면선형 DXF")
    parser.add_argument("--no-guides",action="store_true")
    args=parser.parse_args()
    print(build(args.template,args.output,args.plan_source,not args.no_guides))
