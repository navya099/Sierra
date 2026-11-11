"""v1.6.2: 기존 종단 엔진의 작도 함수를 신규 도곽 document/modelspace에 직접 호출.
기존 최종 출력 파일은 읽지 않음. 기존 프로젝트의 원본 .py는 변경하지 않음.
"""
from pathlib import Path
import argparse
from dataclasses import replace
# R2-6: Use the unified S3-D9 profile engine.
from profile_drawing import create_profile_drawing, DrawingOptions
from profile_transform import DrawingMode
from profile_presets.loader import load_preset, load_preset_file
from profile_presets.runtime import to_drawing_preset
from profile_presets.plan_annotation_style import plan_style_from_preset
from structure_label import ProfileLabelStyle
from profile_calculator import read_ground_points
from dxf_reader import extract_profile
from .combined_plan_profile_v1_7_core import generate, read_alignment
from .plan_entities_v1_7 import render_plan_entities, DEFAULT_LAYERS, _station_of_point
from .plan_ip_lines_v1_8a import render_ip_lines
from .plan_ip_labels_v1_8b import render_ip_labels
from .plan_vip_annotations import render_plan_vips
# v1.8-B.1: IP text/table hook is integrated in render_plan().
from .titleblock_attributes_v1_9a import load_titleblock_config
import ezdxf
from .structure_inputs_b8 import load_structures, load_drawing_settings
from .plan_structure_renderer_b9 import build_structure_cache, render_structure_sheet
from .vertical_curve_inputs_b10 import load_vertical_curve_csv
from .vertical_curve_inputs_b11 import load_simple_vertical_curves
from datetime import datetime
from time import perf_counter
# G1-2D-5-LOG1 filter
import sys

#P-3-B ADD extract_with_stations
from alignment_reader import extract_with_stations

class SierraLogFilter:
    DEBUG_PREFIXES = (
        "[성능]", "[FL GLOBAL_WIDTH]", "[곡선제원/인출선]",
        "[IP교점선]", "[IP문자/제원표]", "[평면 VIP/구배]",
        "[B.9 평면 구조물]", "[B.13]", "[도각 속성]",
        "[G1-2D-4-FIX2]",
    )

    def __init__(self, stream):
        self.stream = stream
        self.pending = ""

    def write(self, text):
        self.pending += str(text)
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            stripped = line.lstrip()
            titleblock_detail = line.startswith("  ") and " → " in line and " : " in line
            if not (stripped.startswith(self.DEBUG_PREFIXES) or titleblock_detail):
                self.stream.write(line + "\n")
        return len(text)

    def flush(self):
        if self.pending:
            self.stream.write(self.pending)
            self.pending = ""
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def _prepare_plan_context(plan, structures, structure_settings_json, station_origin, *,
                          label_style=None, horizontal_scale=1000.):
    t0=perf_counter()
    source_doc=ezdxf.readfile(str(plan))
    from plan_geometry import read_fl
    fl_points, fl_distances = read_fl(source_doc)
    fl_ents = [e for e in source_doc.modelspace().query('LWPOLYLINE')
               if e.dxf.layer.casefold() == 'fl']
    fl_global_width = float(fl_ents[0].dxf.get('const_width', 0.0))
    print(f"[성능] PLAN 원본 읽기+FL: {perf_counter()-t0:.2f}초",flush=True)
    plan_structure_cache = build_structure_cache(
        structures, fl_points, fl_distances, station_origin, structure_settings_json,
        label_style=label_style, horizontal_scale=horizontal_scale, drawing_mode=DrawingMode.CAD
    ) if structures else None
    # Project source station annotations only once; reuse across all sheets.
    t0=perf_counter()
    from plan_station_index import FLStationIndex
    station_index=FLStationIndex(fl_points,fl_distances,station_origin)
    station_cache={}
    station_layers={'km심볼','200심볼','km문자','200문자','보조측점','보조심볼','보조문자','곡선인출선'}
    for ent in source_doc.modelspace():
        layer=ent.dxf.layer.casefold()
        if layer not in station_layers: continue
        typ=ent.dxftype()
        if layer=='곡선인출선' and typ=='LINE':
            sta0, offset0 = station_index.project(ent.dxf.start)
            sta1, offset1 = station_index.project(ent.dxf.end)
            station_cache[ent.dxf.handle] = ((sta0, offset0) if offset0 <= offset1 else (sta1, offset1))
            continue
        elif layer=='보조측점' and typ=='LINE':
            anchor=((ent.dxf.start.x+ent.dxf.end.x)/2,(ent.dxf.start.y+ent.dxf.end.y)/2)
        elif typ=='CIRCLE': anchor=ent.dxf.center
        elif typ in ('TEXT','MTEXT'): anchor=ent.dxf.insert
        else: continue
        station_cache[ent.dxf.handle]=station_index.project(anchor)
    print(f"[성능] PLAN 측점 캐시: {len(station_cache)}개 / {perf_counter()-t0:.2f}초",flush=True)
    return source_doc, fl_points, fl_distances, fl_global_width, plan_structure_cache, station_cache

def _prepare_vertical_curves(
    vip, vertical_curve_csv, vertical_curve_sta_json,
    vertical_curve_index_json, vertical_curve_simple_csv
):
    vc_lengths = {}
    vc_sources = [("GUI CSV", vertical_curve_csv), ("측점 JSON", vertical_curve_sta_json),
                  ("인덱스 JSON", vertical_curve_index_json), ("간편 CSV", vertical_curve_simple_csv)]
    selected = [(label, path) for label, path in vc_sources if path is not None]
    if len(selected) > 1:
        raise ValueError("종곡선 입력 옵션은 한 번에 하나만 지정하세요: " + ", ".join(label for label,_ in selected))
    if vertical_curve_csv:
        vc_lengths, vc_alignment = load_vertical_curve_csv(vertical_curve_csv, vip)
        print(f"[B.10 종곡선] {len(vc_alignment.curves)}개 로드: " + ", ".join(f"VIP {c.vip_index} STA {c.vip_sta:.3f}, L={c.length:g}m, PVC={c.pvc_sta:.3f}, PVT={c.pvt_sta:.3f}" for c in vc_alignment.curves), flush=True)
    elif selected:
        label, path = selected[0]
        mode = {"측점 JSON": "station-json", "인덱스 JSON": "index-json", "간편 CSV": "simple-csv"}[label]
        vc_lengths, vc_alignment = load_simple_vertical_curves(path, vip, mode)
        print(f"[B.11 종곡선 {label}] {len(vc_alignment.curves)}개 로드: " + ", ".join(
            f"VIP {c.vip_index} STA {c.vip_sta:.3f}, L={c.length:g}m, PVC={c.pvc_sta:.3f}, PVT={c.pvt_sta:.3f}"
            for c in vc_alignment.curves), flush=True)
    return vc_lengths


def build(template,plan,profile,output_dir,sheet_length=200.,horizontal_scale=1000.,
          vertical_scale=400.,station_origin=0.,start_sta=None,end_sta=None,
          project_name=None,route_name=None,titleblock_config_path=None,
          left_direction="서울쪽",right_direction="부산쪽",
          structures_csv=None,structure_settings_json=None,vertical_curve_csv=None,
          vertical_curve_sta_json=None,vertical_curve_index_json=None,vertical_curve_simple_csv=None,
          structure_label_preset=None):
    titleblock_config=load_titleblock_config(titleblock_config_path)
    structures=load_structures(structures_csv) if structures_csv else None
    structure_kwargs=load_drawing_settings(structure_settings_json) if structures else {}
    # G1-2D-3: import ONLY the S3-D9 structure annotation style.
    # Never replace combined-sheet origins, band heights, datum or plot limits.
    # REG2-2-C: Load CAD preset and plan annotation style independently of structures.
    if structure_label_preset:
        source_preset = load_preset_file(structure_label_preset, expected_mode='cad',
                                         expected_scales=(horizontal_scale, vertical_scale))
    else:
        source_preset = load_preset('cad', horizontal_scale, vertical_scale)
    plan_annotation_style = plan_style_from_preset(source_preset)
    # REG2-2-D will pass plan_annotation_style to plan renderers.
    plan_label_style = None
    if structures:
        drawing_preset = to_drawing_preset(source_preset)
        style_config = drawing_preset.get('_s3d8_structure_label')
        if style_config is None:
            raise ValueError('선택한 프리셋에 구조물 주석 스타일이 없습니다.')
        label_style = ProfileLabelStyle.from_preset(style_config)
        label_style.validate()
        structure_kwargs['structure_label_style'] = label_style
        # The optional plan-specific section overrides the shared legacy style.
        # Use the validated source JSON (runtime drawing preset only exposes profile style).
        plan_label_style = source_preset.get('layout', {}).get('annotations', {}).get('plan_structure_label')
        if plan_label_style is None:
            plan_label_style = label_style  # legacy schema v2 fallback
        else:
            print('[G1-2D-4-FIX2] 독립 평면 주석 프리셋 사용', flush=True)
        print(f'[G1-2D-3 프리셋] {source_preset["name"]} H{horizontal_scale:g}/V{vertical_scale:g}; '
              f'문자={label_style.text_height:g}, 인출선={label_style.vertical_height:g}, '
              f'각도={label_style.leader_angle:g}', flush=True)
    if structures is not None:
        print(f"[B.8 구조물] {len(structures)}개 로드 (교량 {sum(x.kind=='BRIDGE' for x in structures)}, 터널 {sum(x.kind=='TUNNEL' for x in structures)})",flush=True)
    t0=perf_counter()
    ground=read_ground_points(profile);vip=extract_profile(profile)
    print(f"[성능] PROFILE 입력 해석: {perf_counter()-t0:.2f}초",flush=True)
    vc_lengths = _prepare_vertical_curves(
        vip,
        vertical_curve_csv,
        vertical_curve_sta_json,
        vertical_curve_index_json,
        vertical_curve_simple_csv,
    )
    lo=max(ground[0][0],vip[0].sta)
    hi=min(ground[-1][0],vip[-1].sta)
    # PLAN측점과 PROFILE측점이 일치하도록 교집합 적용
    start=max(lo,station_origin) if start_sta is None else start_sta
    # PERF1-B: FL length is available from the shared PLAN context below.
    end=hi if end_sta is None else end_sta
    if start<lo or end>hi:raise ValueError("PROFILE 범위를 벗어나는 측점")
    options=DrawingOptions(origin_x=35.,origin_y=70.,drawing_mode=DrawingMode.CAD,horizontal_scale=horizontal_scale,
        vertical_scale=vertical_scale,plot_lower_y=135.,plot_upper_y=235.,
        sheet_start_sta=start,sheet_end_sta=end,horizontal_alignment_dxf=str(Path(plan).resolve()),elevation_pole_solid=True,elevation_pole_labels=True,elevation_pole_at_datum_breaks=True)
    # P3-B
    if options.horizontal_alignment_dxf and options.include_alignment_placeholder:
        t0 = perf_counter()
        alignment_data = extract_with_stations(options.horizontal_alignment_dxf)
        print(
            f"[성능] Alignment 공통 전처리: "
            f"{perf_counter() - t0:.2f}초 "
            f"(IP {alignment_data['ip_count']}개)",
            flush=True,
        )

    def render(doc,a,b,index):
        local=replace(options,sheet_start_sta=a,sheet_end_sta=b)
        t0=perf_counter()

        #P3-B
        create_profile_drawing(
            profile,
            Path(output_dir) / f"unused_{index}.dxf",
            local,
            vertical_curve_lengths=vc_lengths,
            structures=structures,
            target_doc=doc,
            alignment_data=alignment_data,
            profile_ground_points=ground, # P4-A
            profile_vip=vip,
            **structure_kwargs,
        )

        print(f"[성능] {index}시트 PROFILE 작도: {perf_counter()-t0:.2f}초",flush=True)
    source_doc, fl_points, fl_distances, fl_global_width, plan_structure_cache, station_cache = (
        _prepare_plan_context(
            plan, structures, structure_settings_json, station_origin,
            label_style=plan_label_style, horizontal_scale=horizontal_scale
        )
    )
    if end_sta is None:
        end=min(end,station_origin+fl_distances[-1])
    if start >= end:
        raise ValueError('PLAN/PROFILE 공통 측점 범위가 비어 있습니다')
    prepared_plan=(fl_points,fl_distances,fl_global_width)
    # PERF1-D1: preselect source annotations once; preserve modelspace ordering.
    # Station filtering and clipping remain unchanged inside the renderer.
    _annotation_layers={name.casefold() for name in DEFAULT_LAYERS
                        if name.casefold() not in ('ip교점선','ip문자')}
    source_annotation_entities=tuple(
        ent for ent in source_doc.modelspace()
        if ent.dxf.get('layer','0').casefold() in _annotation_layers
    )
    print(f'[성능] PLAN 주석 사전 분류: {len(source_annotation_entities)}개',flush=True)
    def render_plan(doc,a,b,index,transform,angle):
        t0=perf_counter()
        # REG1-FIX2: CAD H1000 기준 평면 영역을 축척에 맞게 확대
        frame_factor = horizontal_scale / 1000.0
        plan_rect = (
            70.0 * frame_factor,
            330.0 * frame_factor,
            770.0 * frame_factor,
            530.0 * frame_factor,
        )

        plan_counts=render_plan_entities(source_doc,doc,transform,angle,horizontal_scale,
                             sheet_start=a,sheet_end=b,fl_points=fl_points,
                             fl_distances=fl_distances,station_origin=station_origin,station_cache=station_cache,
                             layers=tuple(x for x in DEFAULT_LAYERS if x.casefold() not in ('ip교점선','ip문자')),
                             plan_rect=plan_rect, plan_style=plan_annotation_style,source_entities=source_annotation_entities)
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

        #REG2
        vip_scale = horizontal_scale / 1000.0

        vip_count = render_plan_vips(
            doc, vip, transform,
            sheet_start=a,
            sheet_end=b,
            fl_points=fl_points,
            fl_distances=fl_distances,
            station_origin=station_origin,
            stem=30.0 * vip_scale,
            arm=10.5 * vip_scale,
            text_height=3.0 * vip_scale,
            plan_rect=plan_rect,
        )
        print(f"[평면 VIP/구배] {index}시트: {vip_count}개",flush=True)
        if plan_structure_cache is not None:
            result=render_structure_sheet(doc,plan_structure_cache,transform,a,b,station_origin,fl_points,fl_distances)
            print(f"[B.9 평면 구조물] {index}시트: {result}",flush=True)
    return generate(template,plan,output_dir,station_origin=station_origin,
         start_sta=start,end_sta=end,sheet_length=sheet_length,
         horizontal_scale=horizontal_scale,vertical_scale=vertical_scale,
         project_name=project_name,route_name=route_name,titleblock_config=titleblock_config,
         profile_hook=render,plan_hook=render_plan,
         left_direction=left_direction,right_direction=right_direction,
         drawing_mode=DrawingMode.CAD,
         prepared_plan=prepared_plan)

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
    p.add_argument("--left-direction",default="서울쪽",help="좌측 방향명")
    p.add_argument("--right-direction",default="부산쪽",help="우측 방향명")
    p.add_argument("--vertical-curve-csv",type=Path,help="원본 GUI에서 내보낸 vertical_curve_result.csv (선택)")
    p.add_argument("--vertical-curve-sta-json",type=Path,help="VIP 측점(m): 종곡선 길이(m) JSON")
    p.add_argument("--vertical-curve-index-json",type=Path,help="0부터 시작하는 VIP 인덱스: 종곡선 길이(m) JSON")
    p.add_argument("--vertical-curve-simple-csv",type=Path,help="간편 CSV: VIP_STA,L 또는 VIP,L")
    p.add_argument("--structures-csv",type=Path,help="기존 구조물 GUI에서 저장한 CSV (미지정 시 B.7 동작 유지)")
    p.add_argument("--structure-settings-json",type=Path,help="거더/교각/터널/주석 설정 JSON (선택)")
    p.add_argument("--structure-label-preset",type=Path,help="S3-D9 CAD 프리셋 JSON (생략 시 축척별 내장 프리셋)")
    p.add_argument("--debug-log", action="store_true", help="상세 로그 표시")
    a=p.parse_args()
    if not a.debug_log:
        sys.stdout = SierraLogFilter(sys.stdout)
    started_at = datetime.now()
    started_tick = perf_counter()
    print(f"[시작시간] {started_at:%Y-%m-%d %H:%M:%S}", flush=True)
    try:
        for item in build(a.template,a.plan,a.profile,a.output_dir,a.sheet_length,
            a.horizontal_scale,a.vertical_scale,a.station_origin,a.start_sta,a.end_sta,
            a.project_name,a.route_name,a.titleblock_config,
            a.left_direction,a.right_direction,
            a.structures_csv,a.structure_settings_json,a.vertical_curve_csv,
            a.vertical_curve_sta_json,a.vertical_curve_index_json,a.vertical_curve_simple_csv,
            a.structure_label_preset):
            if isinstance(item, tuple) and len(item) >= 3:
                output_file, sheet_start, sheet_end = item[:3]
                print(f"[시트 완료] {Path(output_file).name} | STA {sheet_start:g}~{sheet_end:g}m", flush=True)
            else:
                print(item, flush=True)
    finally:
        finished_at = datetime.now()
        elapsed = perf_counter() - started_tick
        minutes, seconds = divmod(elapsed, 60)
        print(f"[완료시간] {finished_at:%Y-%m-%d %H:%M:%S}", flush=True)
        print(f"[걸린시간] {int(minutes)}분 {seconds:.2f}초 (총 {elapsed:.2f}초)", flush=True)
