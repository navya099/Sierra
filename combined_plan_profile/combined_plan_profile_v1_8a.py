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
from .plan_entities_v1_7 import render_plan_entities, DEFAULT_LAYERS
from .plan_ip_lines_v1_8a import render_ip_lines
import ezdxf

def build(template,plan,profile,output_dir,sheet_length=200.,horizontal_scale=1000.,
          vertical_scale=400.,station_origin=0.,start_sta=None,end_sta=None):
    ground=read_ground_points(profile);vip=extract_profile(profile)
    lo=max(ground[0][0],vip[0].sta)
    hi=min(ground[-1][0],vip[-1].sta)
    # PLAN측점과 PROFILE측점이 일치하도록 교집합 적용
    start=max(lo,station_origin) if start_sta is None else start_sta
    end=min(hi,station_origin+read_plan_length(plan)) if end_sta is None else end_sta
    if start<lo or end>hi:raise ValueError("PROFILE 범위를 벗어나는 측점")
    options=DrawingOptions(origin_x=35.,origin_y=70.,horizontal_scale=horizontal_scale,
        vertical_scale=vertical_scale,plot_lower_y=135.,plot_upper_y=235.,
        sheet_start_sta=start,sheet_end_sta=end)
    def render(doc,a,b,index):
        local=replace(options,sheet_start_sta=a,sheet_end_sta=b)
        create_profile_drawing(profile,Path(output_dir)/f"unused_{index}.dxf",
                               local,target_doc=doc)
    source_doc=ezdxf.readfile(str(plan))
    fl_points, fl_distances = read_alignment(plan)
    def render_plan(doc,a,b,index,transform,angle):
        render_plan_entities(source_doc,doc,transform,angle,horizontal_scale,
                             sheet_start=a,sheet_end=b,fl_points=fl_points,
                             fl_distances=fl_distances,station_origin=station_origin,
                             layers=tuple(x for x in DEFAULT_LAYERS if x.casefold()!='ip교점선'.casefold()))
        render_ip_lines(source_doc,doc,transform,sheet_start=a,sheet_end=b,
                        fl_points=fl_points,fl_distances=fl_distances,
                        station_origin=station_origin)
    return generate(template,plan,output_dir,station_origin=station_origin,
         start_sta=start,end_sta=end,sheet_length=sheet_length,
         horizontal_scale=horizontal_scale,profile_hook=render,plan_hook=render_plan)

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
    a=p.parse_args()
    for item in build(a.template,a.plan,a.profile,a.output_dir,a.sheet_length,
        a.horizontal_scale,a.vertical_scale,a.station_origin,a.start_sta,a.end_sta):print(item)
