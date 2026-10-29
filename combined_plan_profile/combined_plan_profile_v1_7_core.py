"""v1.7 좌측 시작점 정렬 PLAN 엔진: 실제 FL 측점별 절단/회전/축척/영역 클리핑.
종단면도 영역은 예약만 하며 기존 final_plan / final_result는 변경하지 않음.
"""
from pathlib import Path
import argparse, math, sys
from time import perf_counter
import ezdxf
from ezdxf.math import Vec2
from .titleblock_attributes_v1_9a import update_titleblock

PLAN_RECT=(35.,330.,811.,530.)
PROFILE_RECT=(35.,70.,811.,315.)

def read_fl_global_width(path):
    """Read the source FL LWPOLYLINE Global Width in source drawing units."""
    doc=ezdxf.readfile(str(path))
    ents=[e for e in doc.modelspace().query("LWPOLYLINE") if e.dxf.layer.casefold()=="fl"]
    if len(ents)!=1: raise ValueError(f"FL LWPOLYLINE 1개 필요: {len(ents)}개")
    return float(ents[0].dxf.get("const_width", 0.0))

def read_alignment(path):
    doc=ezdxf.readfile(str(path))
    ents=[e for e in doc.modelspace().query('LWPOLYLINE') if e.dxf.layer.casefold()=='fl']
    if len(ents)!=1: raise ValueError(f"FL LWPOLYLINE 1개 필요: {len(ents)}개")
    e=ents[0]
    if e.closed or any(abs(b)>1e-12 for _,_,b in e.get_points('xyb')):
        raise ValueError("FL은 열린 직선 LWPOLYLINE이어야 합니다")
    pts=[tuple(map(float,p)) for p in e.get_points('xy')]
    clean=[pts[0]]; dist=[0.]
    for p in pts[1:]:
        d=math.dist(clean[-1],p)
        if d>1e-8: clean.append(p);dist.append(dist[-1]+d)
    if len(clean)<2: raise ValueError("FL 길이 0")
    return clean,dist

def position_at(s,pts,ds):
    if s < -1e-7 or s>ds[-1]+1e-7: raise ValueError("측점이 FL 범위 밖")
    from bisect import bisect_right
    s=max(0.,min(s,ds[-1]))
    i=min(bisect_right(ds,s)-1,len(ds)-2)
    t=(s-ds[i])/(ds[i+1]-ds[i])
    a,b=pts[i],pts[i+1]
    return (a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))

def clip(a,b,rect):
    xmin,ymin,xmax,ymax=rect; dx=b[0]-a[0];dy=b[1]-a[1]
    t0,t1=0.,1.
    for p,q in ((-dx,a[0]-xmin),(dx,xmax-a[0]),(-dy,a[1]-ymin),(dy,ymax-a[1])):
        if abs(p)<1e-12:
            if q<0:return None
        else:
            r=q/p
            if p<0:t0=max(t0,r)
            else:t1=min(t1,r)
            if t0>t1:return None
    return ((a[0]+dx*t0,a[1]+dy*t0),(a[0]+dx*t1,a[1]+dy*t1))

def sheet_ranges(start,end,length):
    if not (math.isfinite(start) and math.isfinite(end) and math.isfinite(length)) or end<=start or length<=0:
        raise ValueError("측점 범위와 시트 길이를 확인하세요")
    n=math.ceil((end-start)/length-1e-10)
    if n>10000:raise ValueError("시트 10000장 초과")
    return [(start+i*length,min(end,start+(i+1)*length)) for i in range(n)]

def generate(template,plan,output_dir,*,station_origin=0.,start_sta=None,end_sta=None,
             sheet_length=200.,horizontal_scale=1000.,rotation="auto",guides=True, profile_hook=None, plan_hook=None,
             vertical_scale=400., project_name=None, route_name=None, titleblock_config=None):
    if horizontal_scale<=0:raise ValueError("축척은 양수여야 합니다")
    pts,ds=read_alignment(plan)
    fl_global_width=read_fl_global_width(plan)
    if not math.isfinite(fl_global_width) or fl_global_width < 0:
        raise ValueError(f"FL GLOBAL_WIDTH 값이 올바르지 않습니다: {fl_global_width}")
    start=station_origin if start_sta is None else start_sta
    end=station_origin+ds[-1] if end_sta is None else end_sta
    if start<station_origin-1e-7 or end>station_origin+ds[-1]+1e-7:
        raise ValueError("측점 범위가 FL 외부입니다")
    if Path(template).resolve()==Path(plan).resolve():raise ValueError("템플릿과 선형 파일은 별도여야 합니다")
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    results=[]
    ranges=sheet_ranges(start,end,sheet_length)
    for number,(sa,sb) in enumerate(ranges,1):
        doc=ezdxf.readfile(str(template));msp=doc.modelspace();doc.header['$INSUNITS']=4
        for name,color in [('ZPP_PLAN_CENTER',1),('ZPP_PLAN_AREA',3),('ZPP_PROFILE_AREA',5),('ZPP_GUIDE_LABEL',7)]:
            if name not in doc.layers:doc.layers.new(name,dxfattribs={'color':color})
        if guides:
            for name,r in [('PLAN',PLAN_RECT),('PROFILE',PROFILE_RECT)]:
                x0,y0,x1,y1=r
                msp.add_lwpolyline([(x0,y0),(x1,y0),(x1,y1),(x0,y1)],close=True,
                    dxfattribs={'layer':f'ZPP_{name}_AREA'})
            msp.add_text(f"PLAN STA {sa:.3f} - {sb:.3f}",
                dxfattribs={'layer':'ZPP_GUIDE_LABEL','height':4,'insert':(40,517)})
        # 기준방향은 시트 시작~종료점 벡터. 기존 DXF 회전이 아닌 신규 좌표 계산
        pa=position_at(sa-station_origin,pts,ds)
        pb=position_at(sb-station_origin,pts,ds)
        if rotation=="auto":
            vx,vy=pb[0]-pa[0],pb[1]-pa[1]
            if math.hypot(vx,vy)<1e-9:
                raise ValueError("시트 시작/종료 좌표 동일: 회전 방향 계산 불가")
            angle=math.atan2(vy,vx)
        else:angle=math.radians(float(rotation))
        ca,sa_s=math.cos(angle),math.sin(angle)
        anchor=pa  # 시트 시작 측점을 종단면도와 동일한 X=70mm에 배치
        cx=70.;cy=(PLAN_RECT[1]+PLAN_RECT[3])/2
        scale=1000./horizontal_scale
        def transform(p):
            dx,dy=p[0]-anchor[0],p[1]-anchor[1]
            return (cx+(dx*ca+dy*sa_s)*scale,cy+(-dx*sa_s+dy*ca)*scale)
        # 시트 경계에서 FL을 정확히 자른 후 도면 좌표로 변환
        station_list=[sa]+[station_origin+d for d in ds if sa+1e-8<station_origin+d<sb-1e-8]+[sb]
        segment_count=0
        fl_sheet_width=fl_global_width*scale
        for a,b in zip(station_list,station_list[1:]):
            u=transform(position_at(a-station_origin,pts,ds))
            v=transform(position_at(b-station_origin,pts,ds))
            clipped=clip(u,v,PLAN_RECT)
            if clipped and math.dist(*clipped)>1e-8:
                # Use LWPOLYLINE, not LINE: AutoCAD Global Width is a polyline property.
                msp.add_lwpolyline(clipped, dxfattribs={
                    'layer':'ZPP_PLAN_CENTER', 'const_width':fl_sheet_width})
                segment_count+=1
        print(f"[FL GLOBAL_WIDTH] {number}시트: 원본={fl_global_width:g}, 출력={fl_sheet_width:g}, 구간={segment_count}",flush=True)
        if plan_hook is not None:
            plan_hook(doc, sa, sb, number, transform, angle)
        if profile_hook is not None:
            profile_hook(doc, sa, sb, number)
        updated = update_titleblock(doc, number=number, total=len(ranges),
            sheet_start=sa, sheet_end=sb, horizontal_scale=horizontal_scale,
            vertical_scale=vertical_scale, project_name=project_name, route_name=route_name,
            drawing_title=(titleblock_config or {}).get("drawing_title", "종평면도"),
            custom_attributes=(titleblock_config or {}).get("attributes", {}))
        print(f"[도각 속성] {number}시트: {len(updated['changes'])}개 값 변경 / {sum(updated['counts'].values())}개 태그 일치", flush=True)
        for tag, before, after in updated['changes']:
            print(f"  {tag:<18}: {before!r} → {after!r}", flush=True)
        path=out/f"종평면도({number}).dxf"
        if path.resolve() in (Path(template).resolve(),Path(plan).resolve()):
            raise ValueError("입력 파일 덮어쓰기 방지")
        t0=perf_counter()
        doc.saveas(str(path))
        print(f"[성능] {number}시트 DXF 저장: {perf_counter()-t0:.2f}초",flush=True)
        t0=perf_counter()
        audit=ezdxf.readfile(str(path)).audit()
        print(f"[성능] {number}시트 DXF 재읽기+감사: {perf_counter()-t0:.2f}초",flush=True)
        if audit.errors:raise RuntimeError(f"DXF 감사 오류 {len(audit.errors)}: {path}")
        results.append((path,sa,sb,segment_count))
    return results

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--template",type=Path,default=Path(__file__).with_name("도각.dxf"))
    p.add_argument("--plan",type=Path,required=True,help="FL LWPOLYLINE을 포함하는 실제 평면선형 DXF")
    p.add_argument("--output-dir",type=Path,default=Path(__file__).parent/"출력")
    p.add_argument("--station-origin",type=float,default=0.)
    p.add_argument("--start-sta",type=float)
    p.add_argument("--end-sta",type=float)
    p.add_argument("--sheet-length",type=float,default=200.)
    p.add_argument("--horizontal-scale",type=float,default=1000.)
    p.add_argument("--rotation",default="auto",help="auto 또는 각도(도)")
    args=p.parse_args()
    for item in generate(args.template,args.plan,args.output_dir,
        station_origin=args.station_origin,start_sta=args.start_sta,end_sta=args.end_sta,
        sheet_length=args.sheet_length,horizontal_scale=args.horizontal_scale,rotation=args.rotation):
        print(item)
