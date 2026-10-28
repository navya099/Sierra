"""v1.6 real DXF input and sheet preflight; v1.4.2 engine unchanged."""
from pathlib import Path
import argparse, json, math, sys
from combined_plan_profile.combined_plan_profile_v1_6_2 import build
from combined_plan_profile.combined_plan_profile_v1_6_core import read_alignment, sheet_ranges
from combined_plan_profile.profile_engine.profile_calculator import read_ground_points
from combined_plan_profile.profile_engine.dxf_reader import extract_profile

ROOT=Path(__file__).resolve().parent
PKG=ROOT/'combined_plan_profile'

def preflight(plan,profile,template,station_origin=0.,start_sta=None,end_sta=None,sheet_length=200.):
    for name,path in [('PLAN',plan),('PROFILE',profile),('도곽',template)]:
        if not Path(path).is_file():raise FileNotFoundError(f'{name} 입력 파일 없음: {path}')
    if not all(math.isfinite(x) for x in (station_origin,sheet_length)) or sheet_length<=0:
        raise ValueError('측점 원점과 시트 길이를 확인하세요')
    points,dist=read_alignment(plan)
    ground=read_ground_points(profile);vip=extract_profile(profile)
    plan_lo,plan_hi=station_origin,station_origin+dist[-1]
    profile_lo,profile_hi=max(ground[0][0],vip[0].sta),min(ground[-1][0],vip[-1].sta)
    lo=max(plan_lo,profile_lo);hi=min(plan_hi,profile_hi)
    a=lo if start_sta is None else start_sta
    b=hi if end_sta is None else end_sta
    if a<lo-1e-7 or b>hi+1e-7 or b<=a:raise ValueError(f'유효 공통 측점 범위 {lo:.3f}~{hi:.3f}m, 요청 {a:.3f}~{b:.3f}m')
    ranges=sheet_ranges(a,b,sheet_length)
    return {'plan_extent':[plan_lo,plan_hi],'profile_extent':[profile_lo,profile_hi],
            'common_extent':[lo,hi],'selected_extent':[a,b], 'sheet_ranges':ranges}

def main():
    p=argparse.ArgumentParser(description='v1.6.2 실제 노선 DXF 입력 검증 및 통합 종평면도 생성')
    p.add_argument('--plan',type=Path,required=True,help='FL 중심선이 있는 원본 평면 DXF')
    p.add_argument('--profile',type=Path,required=True,help='PLAN_PROFILE/지반고 데이터가 있는 원본 종단 DXF')
    p.add_argument('--template',type=Path,default=PKG/'도각.dxf')
    p.add_argument('--output-dir',type=Path,default=PKG/'출력')
    p.add_argument('--station-origin',type=float,default=0.)
    p.add_argument('--start-sta',type=float)
    p.add_argument('--end-sta',type=float)
    p.add_argument('--sheet-length',type=float,default=200.)
    p.add_argument('--horizontal-scale',type=float,default=1000.)
    p.add_argument('--vertical-scale',type=float,default=400.)
    p.add_argument('--dry-run',action='store_true',help='파일 생성 없이 범위와 시트 분할만 확인')
    args=p.parse_args()
    if args.horizontal_scale<=0 or args.vertical_scale<=0: p.error('축척은 양수여야 합니다')
    try:
        report=preflight(args.plan,args.profile,args.template,args.station_origin,args.start_sta,args.end_sta,args.sheet_length)
        print('사전 검증:',json.dumps(report,ensure_ascii=False,indent=2))
        if args.dry_run:return 0
        for result in build(args.template,args.plan,args.profile,args.output_dir,
                args.sheet_length,args.horizontal_scale,args.vertical_scale,
                args.station_origin,*report['selected_extent']):print(result)
        return 0
    except (ValueError,FileNotFoundError) as exc:
        print(f'입력 검증 실패: {exc}',file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
