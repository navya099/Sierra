"""v1.6.2: 기존 종단 엔진의 작도 함수를 신규 도곽 document/modelspace에 직접 호출.
기존 최종 출력 파일은 읽지 않음. 기존 프로젝트의 원본 .py는 변경하지 않음.
"""
from pathlib import Path
import argparse
from dataclasses import replace
from .profile_engine.profile_drawing import create_profile_drawing, DrawingOptions
from .profile_engine.profile_calculator import read_ground_points
from .profile_engine.dxf_reader import extract_profile
from .combined_plan_profile_v1_7_core import generate, read_alignment
from .plan_entities_v1_7 import render_plan_entities, DEFAULT_LAYERS, _station_of_point
from .plan_ip_lines_v1_8a import render_ip_lines
from .plan_ip_labels_v1_8b import render_ip_labels
# v1.8-B.1: IP text/table hook is integrated in render_plan().
from .titleblock_attributes_v1_9a import load_titleblock_config
import ezdxf
from datetime import datetime
from time import perf_counter

def build(template,plan,profile,output_dir,sheet_length=200.,horizontal_scale=1000.,
          vertical_scale=400.,station_origin=0.,start_sta=None,end_sta=None,
          project_name=None,route_name=None,titleblock_config_path=None):
    titleblock_config=load_titleblock_config(titleblock_config_path)
    t0=perf_counter()
    ground=read_ground_points(profile);vip=extract_profile(profile)
    print(f"[성능] PROFILE 입력 해석: {perf_counter()-t0:.2f}초",flush=True)
    lo=max(ground[0][0],vip[0].sta)
    hi=min(ground[-1][0],vip[-1].sta)
    # PLAN측점과 PROFILE측점이 일치하도록 교집합 적용
    start=max(lo,station_origin) if start_sta is None else start_sta
    end=min(hi,station_origin+read_plan_length(plan)) if end_sta is None else end_sta
    if start<lo or end>hi:raise ValueError("PROFILE 범위를 벗어나는 측점")
    options=DrawingOptions(origin_x=35.,origin_y=70.,horizontal_scale=horizontal_scale,
        vertical_scale=vertical_scale,plot_lower_y=135.,plot_upper_y=235.,
        sheet_start_sta=start,sheet_end_sta=end,elevation_pole_solid=True,elevation_pole_labels=True)
    def render(doc,a,b,index):
        local=replace(options,sheet_start_sta=a,sheet_end_sta=b)
        t0=perf_counter()
        create_profile_drawing(profile,Path(output_dir)/f"unused_{index}.dxf",
                               local,target_doc=doc)
        print(f"[성능] {index}시트 PROFILE 작도: {perf_counter()-t0:.2f}초",flush=True)
    t0=perf_counter()
    source_doc=ezdxf.readfile(str(plan))
    fl_points, fl_distances = read_alignment(plan)
    print(f"[성능] PLAN 원본 읽기+FL: {perf_counter()-t0:.2f}초",flush=True)
    # Project source station annotations only once; reuse across all sheets.
    t0=perf_counter()
    station_cache={}
    station_layers={'km심볼','200심볼','km문자','200문자','보조측점'}
    for ent in source_doc.modelspace():
        layer=ent.dxf.layer.casefold()
        if layer not in station_layers: continue
        typ=ent.dxftype()
        if layer=='보조측점' and typ=='LINE':
            anchor=((ent.dxf.start.x+ent.dxf.end.x)/2,(ent.dxf.start.y+ent.dxf.end.y)/2)
        elif typ=='CIRCLE': anchor=ent.dxf.center
        elif typ in ('TEXT','MTEXT'): anchor=ent.dxf.insert
        else: continue
        station_cache[ent.dxf.handle]=_station_of_point(anchor,fl_points,fl_distances,station_origin)
    print(f"[성능] PLAN 측점 캐시: {len(station_cache)}개 / {perf_counter()-t0:.2f}초",flush=True)
    def render_plan(doc,a,b,index,transform,angle):
        t0=perf_counter()
        plan_counts=render_plan_entities(source_doc,doc,transform,angle,horizontal_scale,
                             sheet_start=a,sheet_end=b,fl_points=fl_points,
                             fl_distances=fl_distances,station_origin=station_origin,station_cache=station_cache,
                             layers=tuple(x for x in DEFAULT_LAYERS if x.casefold() not in ('ip교점선','ip문자')))
        print(f"[곡선제원/인출선] {index}시트: { {k:v for k,v in plan_counts.items() if k.startswith('curve_')} }",flush=True)
        print(f"[성능] {index}시트 PLAN 객체: {perf_counter()-t0:.2f}초",flush=True)
        t0=perf_counter()
        render_ip_lines(source_doc,doc,transform,sheet_start=a,sheet_end=b,
                        fl_points=fl_points,fl_distances=fl_distances,
                        station_origin=station_origin)
        print(f"[성능] {index}시트 IP교점선: {perf_counter()-t0:.2f}초",flush=True)
        t0=perf_counter()
        ip_labels=render_ip_labels(source_doc,doc,transform,angle,horizontal_scale)
        print(f"[IP문자/제원표] {index}시트: {ip_labels}; 처리 {perf_counter()-t0:.2f}초",flush=True)
    return generate(template,plan,output_dir,station_origin=station_origin,
         start_sta=start,end_sta=end,sheet_length=sheet_length,
         horizontal_scale=horizontal_scale,vertical_scale=vertical_scale,
         project_name=project_name,route_name=route_name,titleblock_config=titleblock_config,
         profile_hook=render,plan_hook=render_plan)

def read_plan_length(plan):
    from .combined_plan_profile_v1_6_core import read_alignment
    return read_alignment(plan)[1][-1]

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--template",type=Path,default=Path(__file__).with_name("도각.dxf"))
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--profile",type=Path,required=True,help="PLAN_PROFILE + GROUND_PROFILE 원본 DXF")
    p.add_argument("--output-dir",type=Path,default=Path(__file__).parent/"출력")
    p.add_argument("--sheet-length",type=float,default=200.)
    p.add_argument("--horizontal-scale",type=float,default=1000.)
    p.add_argument("--vertical-scale",type=float,default=400.)
    p.add_argument("--station-origin",type=float,default=0.)
    p.add_argument("--start-sta",type=float)
    p.add_argument("--end-sta",type=float)
    p.add_argument("--project-name",default=None,help="도각 사업명 (미입력 시 원본 유지)")
    p.add_argument("--route-name",default=None,help="도각 노선명 (미입력 시 원본 유지)")
    p.add_argument("--titleblock-config", type=Path, default=None,
                   help="JSON 도각 속성 설정 파일 (미입력 시 기존 동작 유지)")
    a=p.parse_args()
    started_at = datetime.now()
    started_tick = perf_counter()
    print(f"[시작시간] {started_at:%Y-%m-%d %H:%M:%S}", flush=True)
    try:
        for item in build(a.template,a.plan,a.profile,a.output_dir,a.sheet_length,
            a.horizontal_scale,a.vertical_scale,a.station_origin,a.start_sta,a.end_sta,
            a.project_name,a.route_name,a.titleblock_config):
            print(item, flush=True)
    finally:
        finished_at = datetime.now()
        elapsed = perf_counter() - started_tick
        minutes, seconds = divmod(elapsed, 60)
        print(f"[완료시간] {finished_at:%Y-%m-%d %H:%M:%S}", flush=True)
        print(f"[걸린시간] {int(minutes)}분 {seconds:.2f}초 (총 {elapsed:.2f}초)", flush=True)
