"""U2: KDI rough-only workspace. Frozen roadbed XLSX remains D5 compatible."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from decimal import Decimal
from cost_rough_engine import available_rough, estimate_rough, export_cost_xlsx
from quantity_price import load_config
from earthwork_simple import calculate_earthwork
from profile_calculator import read_ground_points
from system_kdi_link import load_eligible_catalog, provenance
from track_length_link import segment_lengths, quantity_for_price
from long_tunnel_rough import classify_tunnels, segment_key, estimate_long_tunnels

TABS = ('노반','궤도','전차선','전력','송전선로','변전설비','신호','통신','건축')

def _roadbed_track_type(code):
    """Read explicit S/D/E track configuration from verified rough KDI code."""
    import re
    match = re.search(r'_([SDE])_(?:RURAL|URBAN)$', code)
    if not match:
        raise ValueError(f'노반 단가의 단선/복선 조건을 판별할 수 없습니다: {code}')
    return {'S': 1, 'D': 2, 'E': 3}[match.group(1)]

def validate_roadbed_tracks(chosen, track_type):
    for group, code in chosen.items():
        if code and _roadbed_track_type(code) != track_type:
            names = {1:'단선',2:'복선',3:'복선전철'}
            raise ValueError(f'{group}: 선택한 단가({names[_roadbed_track_type(code)]})와 공통 선로형식({names[track_type]})이 다릅니다. 노반 단가를 다시 선택하세요.')

def _eligible_for_track(code, track_type):
    """Only offer rates explicitly compatible with the selected line type.

    Roadbed S/D/E and track S/D/DE are distinct KDI source categories.
    System catenary/power tables distinguish only one/two tracks; E uses two.
    """
    if code.startswith(('EARTH_ROUGH_', 'BRIDGE_ROUGH_', 'TUNNEL_ROUGH_')):
        return _roadbed_track_type(code) == track_type
    if code.startswith('TRACK_ROUGH_'):
        suffix = {1: '_S_', 2: '_D_', 3: '_DE_'}[track_type]
        return suffix in code
    if code.startswith('CAT_ROUGH_'):
        return ('_S_' in code) if track_type == 1 else ('_D_' in code)
    if code.startswith('SIG_'):
        return code.startswith('SIG_S_') if track_type == 1 else code.startswith('SIG_D_')
    if code.startswith('COMM_ROUGH_'):
        variant=code[len('COMM_ROUGH_'):].rsplit('_',1)[0]
        return variant in {1: ('S_NON','S_E'), 2: ('D_NON',), 3: ('D_E','D_CITY')}[track_type]
    if code.startswith('SUB_ROUGH_'):
        return code.startswith('SUB_ROUGH_S_') if track_type == 1 else code.startswith('SUB_ROUGH_D_')
    if code.startswith('ARCH_ROUGH_'):
        return code.startswith({1:'ARCH_ROUGH_S_',2:'ARCH_ROUGH_D_',3:'ARCH_ROUGH_E_'}[track_type])
    if code.startswith('POWER_'):
        return code.startswith('POWER_S_') if track_type == 1 else code.startswith('POWER_D_')
    return True

def select_transmission_band(km):
    """KDI III-90 fixed cost; distance bins (0,10], (10,60], ... (160,170]."""
    if not km.is_finite() or km <= 0:
        raise ValueError('송전선로: 노선연장은 0km보다 커야 합니다.')
    for maximum in (10,60,110,160,170):
        if km <= maximum:
            return f'TRANS_ROUGH_LE{maximum}'
    raise ValueError('송전선로: 170km 초과 노선은 표 Ⅲ-90 적용 범위 밖입니다. 별도 검토가 필요합니다.')

def select_substation_band(km, tracks):
    """KDI III-92 literal ±5km bins; do not interpolate or extrapolate."""
    if not km.is_finite() or km <= 0:
        raise ValueError('변전설비: 노선연장은 0km보다 커야 합니다.')
    # 5km and 10km share an endpoint at 5km; exact 5km uses the 5km row.
    for center in (5,10,20,30,40,50,60,70,80,90,100,110,120,150):
        if abs(km-Decimal(center)) <= Decimal(5):
            return f'SUB_ROUGH_{"S" if tracks==1 else "D"}_{center}'
    raise ValueError(f'변전설비: {km}km는 표 Ⅲ-92의 제시 연장구간 밖입니다. 임의 보간하지 않습니다.')

def _source_catalog():
    import json
    db_path=Path(__file__).with_name('kdi_general_rail_2019.json')
    original=load_eligible_catalog(db_path)
    extra=[r for r in json.loads(db_path.read_text(encoding='utf-8'))['items'] if r.get('group') in ('송전선로','변전설비') and r.get('method')=='ROUGH']
    return original+extra

def _rough_system_rows(catalog, selected, lengths, tracks, stations=None, arch_counts=None):
    """Independent KDI rough-only records; never uses DETAIL rows."""
    lookup={r['code']:r for r in catalog}
    result=[]
    for group,code in selected.items():
        if not code:continue
        row=lookup.get(code)
        if row is None or row['group']!=group or row.get('method')!='ROUGH':
            raise ValueError(f'{group}: 개략 단가가 아닙니다: {code}')
        if row['unit'] not in ('km','개소(역)','식'):raise ValueError(f'{code}: 지원하지 않는 개략 단위입니다.')
        if group=='궤도':
            q=quantity_for_price(row,lengths,tracks,'전체')
            scope='전체'
        elif group=='전차선':
            scope=next((label for suffix,label in (('_EARTH','토공'),('_BRIDGE','교량'),('_TUNNEL','터널')) if code.endswith(suffix)),None)
            if scope is None:raise ValueError(f'{code}: 지세 분류가 없습니다.')
            if ('_D_' in code and tracks!=2) or ('_S_' in code and tracks!=1):
                raise ValueError(f'{code}: 단선/복선 선택이 단가 조건과 다릅니다.')
            q=lengths[scope]/Decimal(1000)
        elif group=='전력':
            scope='터널' if code.endswith('_TUN') else ('교량' if code.endswith('_BRIDGE') else '토공')
            expected=1 if code.startswith('POWER_S_') else 2
            if tracks!=expected:raise ValueError(f'{code}: 선택한 단선/복선 조건과 선로 수가 다릅니다.')
            q=lengths[scope]/Decimal(1000)
        elif group in ('송전선로','변전설비'):
            scope='노선연장 구간';q=Decimal(1)
            km=lengths['전체']/Decimal(1000)
            expected=(select_transmission_band(km) if group=='송전선로' else select_substation_band(km,tracks))
            if code!=expected:raise ValueError(f'{group}: 노선연장 {km}km에 해당하는 KDI 구간 단가가 아닙니다: {code}')
        elif group=='건축':
            scope='정거장'
            if arch_counts is None or code not in arch_counts:raise ValueError('건축 역사 개소수가 없습니다.')
            q=arch_counts[code]
            if q!=q.to_integral_value() or q<0:raise ValueError('건축 역사 개소수는 0 이상의 정수여야 합니다.')
        elif group=='신호':
            if not code.startswith(('SIG_S_GENERAL','SIG_D_GENERAL')):
                raise ValueError('신호 개략단가만 지원합니다.')
            if (code.startswith('SIG_S_') and tracks!=1) or (code.startswith('SIG_D_') and tracks!=2):
                raise ValueError('신호 단가의 선로형식이 일치하지 않습니다.')
            scope='전체';q=lengths['전체']/Decimal(1000)
        elif group=='통신':
            if not code.startswith('COMM_ROUGH_'):raise ValueError('통신 개략단가만 지원합니다.')
            if code.endswith('_KM'):
                scope='전체';q=lengths['전체']/Decimal(1000)
            elif code.endswith('_ST'):
                scope='정거장'
                if stations is None:raise ValueError('통신 정거장 개소수를 입력하세요.')
                if stations!=stations.to_integral_value() or stations<0:
                    raise ValueError('정거장 수량은 0 이상의 정수여야 합니다.')
                q=stations
            else:raise ValueError('통신 단가의 수량 단위가 불명확합니다.')
        else:raise ValueError(f'{group}: 아직 개략 계산을 지원하지 않습니다.')
        if q<=0:raise ValueError(f'{group}: {scope} 수량이 0입니다. 해당 항목을 미선택 처리하세요.')
        price=Decimal(str(row['source_price_krw']))
        result.append({'group':group,'code':code,'name':row['name'], 'scope':scope,
                       'quantity':q,'unit':row['unit'],'unit_price':price,'amount':q*price,
                       'basis':provenance(row,'kdi_general_rail_2019.json')+(f' | [U6 개략] 건축 역사 유형별 {q}개소 (사용자 입력)' if group=='건축' else f' | [U5 개략] KDI 노선연장 {lengths["전체"]}m, 단계별 정액(중간값 미적용)' if scope=='노선연장 구간' else (f' | [U4 개략] 정거장 {stations}개소 (사용자 입력)' if scope=='정거장' else f' | [U4 개략] {scope} {lengths[scope]}m / 1000'))})
    return result

def _build_system_workbook(records,lengths,tracks):
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();summary=wb.active;summary.title='시스템개략총괄'
    summary.append(['공종','산정금액(원)','상태','항목수'])
    for group in ('궤도','전력','전차선','신호','통신','건축','송전선로','변전설비'):
        group_rows=[r for r in records if r['group']==group]
        summary.append([group,float(sum((r['amount'] for r in group_rows),Decimal(0))) if group_rows else None,
                        '산정' if group_rows else '미산정',len(group_rows)])
    summary.append(['산정분 합계',float(sum((r['amount'] for r in records),Decimal(0))), '전체 사업비 아님',len(records)])
    ws=wb.create_sheet('시스템개략내역');ws.append(['공종','단가코드','항목명','구간','수량','단위','원단가(원)','금액(원)','산정 근거'])
    for r in records:ws.append([r['group'],r['code'],r['name'],r['scope'],float(r['quantity']),r['unit'],int(r['unit_price']),float(r['amount']),r['basis']])
    note=wb.create_sheet('산정기준');note.append(['항목','내용'])
    note.append(['가격 기준','KDI 2019 원문 단가, 물가보정 없음'])
    note.append(['선로수',tracks])
    for k,v in lengths.items():note.append([k+' 연장(m)',float(v)])
    note.append(['미산정 주의','미선택 공종은 0원으로 간주하지 않음. 전차선 야간 할증 미적용'])
    note.append(['D5 호환','본 파일은 시스템 개략 보조 산정서이며 기존 D5 노반 입력 파일로 사용하지 않음'])
    for sheet in wb:
        sheet.freeze_panes='A2'
        for c in sheet[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='17365D')
        for col in 'ABCDEFGHI':sheet.column_dimensions[col].width=28 if col!='I' else 90
    return wb

def open_rough_workspace(editor):
    win=tk.Toplevel(editor);win.title('v12.8-S2.5-U8-LONGTUN2 개략 공사비 계산');win.geometry('1100x710');win.minsize(850,550)
    ttk.Label(win,text='KDI 개략 공사비 전용 | 세부 단가 사용 금지',padding=10).pack(anchor='w')
    notebook=ttk.Notebook(win);notebook.pack(fill='both',expand=True,padx=10,pady=5)
    opts=available_rough();catalog=_source_catalog();lookup={};selections={};system_vars={};power_vars={};cat_vars={};trans_enabled=tk.BooleanVar(value=False);sub_enabled=tk.BooleanVar(value=False);signal_var=tk.StringVar();comm_variant=tk.StringVar();station_count=tk.StringVar();filtered_pickers=[];arch_entries=[];long_tunnel_entries={}
    track_type=tk.IntVar(value=1)
    track_count=track_type  # shared choice: 3 (복선전철) uses two tracks in system pricing
    def system_track_count():
        return 1 if track_type.get()==1 else 2
    shared=ttk.LabelFrame(win,text='공통 선로형식 (노반·궤도·전차선·전력·신호·통신·변전설비·건축 적용)',padding=6)
    shared.pack(fill='x',padx=12,pady=(0,4))
    for label,value in (('단선',1),('복선',2),('복선전철',3)):
        ttk.Radiobutton(shared,text=label,variable=track_type,value=value).pack(side='left',padx=14)
    def picker(parent,group,rows,variable):
        choices=['미선택 (미산정)']
        for item in rows:
            label=f"{item['code']} | {item.get('spec','')} | {item.get('condition','')} | {int(item['source_price_krw']):,}원/{item['unit']}"
            choices.append(label);lookup[label]=item['code']
        variable.set(choices[0]);combo=ttk.Combobox(parent,textvariable=variable,values=choices,state='readonly',width=95);combo.pack(fill='x',pady=5)
        filtered_pickers.append((combo,variable,choices))
    for group in TABS:
        frame=ttk.Frame(notebook,padding=14);notebook.add(frame,text=group)
        ttk.Label(frame,text=group+' 개략 공사비',font=('',12,'bold')).pack(anchor='w',pady=(0,10))
        if group=='노반':
            ttk.Label(frame,text='공통 선로형식과 동일한 단가만 적용 가능 · 기존 노반 계산식 및 D5 형식 유지').pack(anchor='w')
            for work in ('토공','교량','터널'):
                row=ttk.Frame(frame,padding=5);row.pack(fill='x')
                ttk.Label(row,text=work,width=9).pack(side='left')
                choices=['미선택 (미산정)']
                for item in opts[work]:
                    label=f"{item['code']} | {item['spec']} | {item['condition']}";choices.append(label);lookup[label]=item['code']
                v=tk.StringVar(value=choices[0]);selections[work]=v
                combo=ttk.Combobox(row,textvariable=v,values=choices,state='readonly',width=95);combo.pack(side='left',fill='x',expand=True)
                filtered_pickers.append((combo,v,choices))
            ttk.Label(frame,text='토공·교량·일반터널은 기존 D5 엔진을 사용합니다. 개별 터널 10km 이상은 표 Ⅲ-77로 별도 계산합니다.',wraplength=850).pack(anchor='w',pady=8)
            ttk.Label(frame,text='초장대터널(10km 이상) · 터널별 경사갱 조건과 방재설비 비율을 입력합니다.',wraplength=850).pack(anchor='w')
            long_frame=ttk.LabelFrame(frame,text='초장대터널별 입력 (구조물 목록에서 자동 감지)',padding=8)
            long_frame.pack(fill='x',pady=8)
            def refresh_long_tunnels():
                for child in long_frame.winfo_children():child.destroy()
                _, longs=classify_tunnels(editor.segments)
                old=dict(long_tunnel_entries);long_tunnel_entries.clear()
                if not longs:
                    ttk.Label(long_frame,text='현재 10km 이상 개별 터널이 없습니다.').pack(anchor='w')
                def build_panel(idx,seg):
                        key=segment_key(seg)
                        prior=old.get(key)
                        if prior:
                            state=prior
                        else:
                            state={'mode':tk.StringVar(value='simple'),'length':tk.StringVar(value=''),
                                   'count':tk.StringVar(value=''),'fire':tk.StringVar(value=''),
                                   'shafts':[]}
                        long_tunnel_entries[key]=state
                        item=ttk.LabelFrame(long_frame,text=f'{seg.name or "터널 "+str(idx)} · STA {seg.start_sta:.1f}~{seg.end_sta:.1f}m · 본선 {seg.length/1000:.3f}km',padding=8)
                        item.pack(fill='x',pady=5)
                        selector=ttk.Frame(item);selector.pack(anchor='w',fill='x',pady=(0,5))
                        ttk.Label(selector,text='경사갱 입력 방식').pack(side='left',padx=(0,12))
                        ttk.Radiobutton(selector,text='간편 입력',variable=state['mode'],value='simple').pack(side='left',padx=(0,12))
                        ttk.Radiobutton(selector,text='경사갱별 입력',variable=state['mode'],value='individual').pack(side='left')
                        mode_frame=ttk.Frame(item);mode_frame.pack(fill='x')
                        total_var=tk.StringVar(value='경사갱 총연장: 입력 대기')
                        def render_mode(st=state,container=mode_frame,output=total_var):
                            for child in container.winfo_children():child.destroy()
                            def update_total(*_args):
                                try:
                                    if st['mode'].get()=='simple':
                                        length=Decimal(st['length'].get().strip());count=Decimal(st['count'].get().strip())
                                        if not length.is_finite() or not count.is_finite() or length<0 or count<0 or count!=count.to_integral_value():raise ValueError
                                        output.set(f'경사갱 총연장: {length*count:g}km = {length:g}km × {int(count)}개소')
                                    else:
                                        values=[Decimal(v.get().strip()) for v in st['shafts']]
                                        if any(not x.is_finite() or x<=0 for x in values):raise ValueError
                                        output.set(f'경사갱 총연장: {sum(values,Decimal(0)):g}km ({len(values)}개소)')
                                except Exception:
                                    output.set('경사갱 총연장: 연장을 입력하세요')
                            if st['mode'].get()=='simple':
                                for col,(label,var,width) in enumerate((('경사갱 1개소당 연장 (km)',st['length'],16),('경사갱 개소수 (개소)',st['count'],12))):
                                    field=ttk.Frame(container);field.grid(row=0,column=col,sticky='w',padx=(0,22))
                                    ttk.Label(field,text=label).pack(anchor='w',pady=(0,3))
                                    ttk.Entry(field,textvariable=var,width=width).pack(anchor='w')
                            else:
                                for i,var in enumerate(st['shafts']):
                                    row=ttk.Frame(container);row.pack(anchor='w',pady=2)
                                    ttk.Label(row,text=f'경사갱 {i+1} 연장 (km)',width=22).pack(side='left')
                                    ttk.Entry(row,textvariable=var,width=15).pack(side='left',padx=5)
                                    ttk.Button(row,text='삭제',command=lambda index=i:remove_shaft(index)).pack(side='left')
                                ttk.Button(container,text='+ 경사갱 추가',command=lambda:add_shaft()).pack(anchor='w',pady=4)
                            update_total()
                            st['_update_total']=update_total
                        def add_shaft(st=state):
                            st['shafts'].append(tk.StringVar(value=''))
                            st['shafts'][-1].trace_add('write',lambda *_:st['_update_total']())
                            render_mode()
                        def remove_shaft(index,st=state):
                            st['shafts'].pop(index)
                            render_mode()
                        state['mode'].trace_add('write',lambda *_:render_mode())
                        for var in (state['length'],state['count']):
                            var.trace_add('write',lambda *_,st=state:st['_update_total']())
                        render_mode()
                        fire_frame=ttk.Frame(item);fire_frame.pack(anchor='w',pady=(7,0))
                        ttk.Label(fire_frame,text='방재설비 적용 비율 (%)').pack(anchor='w',pady=(0,3))
                        ttk.Entry(fire_frame,textvariable=state['fire'],width=15).pack(anchor='w')
                        ttk.Label(item,textvariable=total_var,foreground='#555555').pack(anchor='w',pady=(7,0))
                        ttk.Label(item,text='방재설비는 본선 공사비의 1.0~1.5%를 적용합니다.',foreground='#555555').pack(anchor='w',pady=(2,0))
                for idx,seg in enumerate(longs,1):
                    build_panel(idx,seg)
            ttk.Button(frame,text='구조물 목록에서 초장대터널 갱신',command=refresh_long_tunnels).pack(anchor='w',pady=3)
            refresh_long_tunnels()
        elif group in ('궤도','전력','전차선'):
            ttk.Label(frame,text='선로형식은 창 상단 공통 선택을 사용합니다 (복선전철은 시스템 단가의 복선에 대응).').pack(anchor='w')
            rows=[r for r in catalog if r['group']==group and r.get('method')=='ROUGH']
            if group=='궤도':
                ttk.Label(frame,text='전체 노선연장 × 선택한 KDI 궤도 개략 km 단가 (1개 선택)').pack(anchor='w',pady=8)
                v=tk.StringVar();system_vars[group]=v;picker(frame,group,rows,v)
            elif group=='전차선':
                ttk.Label(frame,text='KDI 표 Ⅲ-94 · 2019년 · 주간 · VAT 제외 | 토공·교량·터널 각각 1개 단가 선택',wraplength=870).pack(anchor='w',pady=8)
                ttk.Label(frame,text='강체가선은 복선 터널에만 원문 단가가 있습니다. 운행선 야간 할증은 미적용.',wraplength=870).pack(anchor='w')
                for scope,suffix in (('토공','_EARTH'),('교량','_BRIDGE'),('터널','_TUNNEL')):
                    ttk.Label(frame,text=scope+' 단가').pack(anchor='w',pady=(8,0))
                    v=tk.StringVar();cat_vars[scope]=v
                    picker(frame,group,[r for r in rows if r['code'].endswith(suffix)],v)
            else:
                ttk.Label(frame,text='KDI 표 Ⅲ-96 · 토공·교량·터널 각각 별도 단가 선택 (교량 단가는 원문에 독립된 행으로 수록).',wraplength=870).pack(anchor='w',pady=8)
                for scope in ('토공','교량','터널'):
                    ttk.Label(frame,text=scope+' 단가').pack(anchor='w',pady=(8,0))
                    v=tk.StringVar();power_vars[scope]=v
                    picker(frame,group,[r for r in rows if (r['code'].endswith('_TUN') if scope=='터널' else r['code'].endswith('_BRIDGE') if scope=='교량' else not r['code'].endswith(('_TUN','_BRIDGE')))],v)
                ttk.Label(frame,text='전력의 토공·교량·터널은 각각 별도 산정하며, 구간별 연장을 중복 적용하지 않습니다.').pack(anchor='w',pady=10)
        elif group in ('송전선로','변전설비'):
            enabled=trans_enabled if group=='송전선로' else sub_enabled
            ttk.Checkbutton(frame,text=f'{group} 개략 공사비 자동 산정',variable=enabled).pack(anchor='w',pady=8)
            ttk.Label(frame,text=('KDI 표 Ⅲ-90 · 전체 노선연장별 정액, 단복선 동일 · 170km 이내' if group=='송전선로' else 'KDI 표 Ⅲ-92 · 노선연장 ±5km 단계별 정액, 단선·복선 구분'),wraplength=850).pack(anchor='w')
            ttk.Label(frame,text='중간값 보간 없음 · 선형 연장으로 자동 단가 선택 · 해당 구간이 없으면 저장 전 오류 표시',wraplength=850).pack(anchor='w',pady=8)
        elif group=='신호':
            ttk.Label(frame,text='KDI 표 Ⅲ-97 · 신설선 차상신호방식 개략 단가 × 전체 노선연장(km)',wraplength=870).pack(anchor='w',pady=8)
            ttk.Label(frame,text='개량사업 1.78배는 자동 적용하지 않습니다. 신설선 기준입니다.',wraplength=870).pack(anchor='w')
            picker(frame,group,[r for r in catalog if r['group']==group and r.get('method')=='ROUGH'],signal_var)
        elif group=='통신':
            ttk.Label(frame,text='KDI 표 Ⅲ-102 · 같은 유형의 연장 단가×km + 정거장 단가×개소수를 합산',wraplength=870).pack(anchor='w',pady=8)
            ttk.Label(frame,text='선로형식에 맞는 통신 유형을 선택하면 km·정거장 단가가 자동으로 한 쌍 적용됩니다.').pack(anchor='w')
            comm_rows=[r for r in catalog if r['group']=='통신' and r.get('method')=='ROUGH']
            variant_labels={
                'S_NON':'단선 비전철','S_E':'단선 전철','D_NON':'복선 비전철',
                'D_E':'복선 전철 간선','D_CITY':'복선 전철 도심'}
            choices=['미선택 (미산정)']+[f'{key} | {label}' for key,label in variant_labels.items()]
            comm_variant.set(choices[0]);comm_combo=ttk.Combobox(frame,textvariable=comm_variant,values=choices,state='readonly',width=75)
            comm_combo.pack(fill='x',pady=8)
            filtered_pickers.append((comm_combo,comm_variant,choices))
            line=ttk.Frame(frame);line.pack(fill='x',pady=10)
            ttk.Label(line,text='정거장 개소수 (필수 · 0 이상의 정수):').pack(side='left')
            ttk.Entry(line,textvariable=station_count,width=12).pack(side='left',padx=8)
            ttk.Label(frame,text='정거장 개소수는 자동 추정하지 않습니다. 역이 0개인 경우 0을 입력하세요.').pack(anchor='w')
        elif group=='건축':
            ttk.Label(frame,text='KDI 표 Ⅲ-86 · 2019년 · 억원/개소 · 제비율 포함, VAT 제외 | 유형별 역사 개소수 입력',wraplength=850).pack(anchor='w',pady=6)
            ttk.Label(frame,text='각 행에서 역사 유형과 개소수를 선택하세요. 같은 유형을 여러 행에서 선택하면 수량을 합산합니다. 미선택 행은 계산하지 않습니다.',wraplength=850).pack(anchor='w')
            arch_rows=[r for r in catalog if r['group']=='건축' and r.get('method')=='ROUGH']
            for i in range(12):
                line=ttk.Frame(frame);line.pack(fill='x',pady=2)
                ttk.Label(line,text=f'역사 {i+1:02d}',width=9).pack(side='left')
                v=tk.StringVar();count=tk.StringVar(value='0')
                choices=['미선택 (미산정)']
                for item in arch_rows:
                    label=f"{item['code']} | {item['spec']} | {item['condition']} | {int(item['source_price_krw']):,}원/{item['unit']}"
                    choices.append(label);lookup[label]=item['code']
                v.set(choices[0]);combo=ttk.Combobox(line,textvariable=v,values=choices,state='readonly',width=85)
                combo.pack(side='left',fill='x',expand=True)
                filtered_pickers.append((combo,v,choices))
                ttk.Label(line,text='개소').pack(side='left',padx=5)
                ttk.Entry(line,textvariable=count,width=6).pack(side='left')
                arch_entries.append((v,count))
        else:
            ttk.Label(frame,text='미산정').pack(anchor='w')
    def refresh_track_filters(*_):
        """Refresh every active trade, retain a valid selection, clear invalid ones."""
        kind=track_type.get()
        for combo,variable,all_choices in filtered_pickers:
            choices=[all_choices[0]] + [label for label in all_choices[1:]
                      if (_eligible_for_track(lookup[label],kind) if label in lookup else
                          (label.split(' | ')[0] in {1: ('S_NON','S_E'), 2: ('D_NON',), 3: ('D_E','D_CITY')}[kind]))]
            current=variable.get()
            combo.configure(values=choices)
            if current not in choices:
                variable.set(choices[0])
    track_type.trace_add('write',refresh_track_filters)
    refresh_track_filters()
    footer=ttk.Frame(win,padding=12);footer.pack(fill='x')
    status=tk.StringVar(value='9개 공종 개략 산정 가능 | 건축: 역사 유형별 개소수 입력')
    ttk.Label(footer,textvariable=status,wraplength=950).pack(anchor='w',pady=(0,8))
    def export():
        try:
            source,alignment=editor.get_context()
            if not source or alignment is None:raise ValueError('먼저 종단 DXF를 불러오고 계산을 완료하세요.')
            chosen={g:lookup.get(v.get(),'') for g,v in selections.items()}
            system_chosen={g:lookup.get(v.get(),'') for g,v in system_vars.items()}
            power_chosen={scope:lookup.get(v.get(),'') for scope,v in power_vars.items()}
            cat_chosen={scope:lookup.get(v.get(),'') for scope,v in cat_vars.items()}
            validate_roadbed_tracks(chosen,track_type.get())
            signal_code=lookup.get(signal_var.get(),'')
            comm_key=comm_variant.get().split(' | ')[0] if ' | ' in comm_variant.get() else ''
            comm_codes=[];stations=None
            if comm_key:
                if not station_count.get().strip():raise ValueError('통신 정거장 개소수를 입력하세요 (0개도 명시 입력).')
                try:stations=Decimal(station_count.get().strip())
                except Exception as exc:raise ValueError('정거장 개소수는 0 이상의 정수여야 합니다.') from exc
                if not stations.is_finite() or stations<0 or stations!=stations.to_integral_value():
                    raise ValueError('정거장 개소수는 0 이상의 정수여야 합니다.')
                if comm_key not in {1:('S_NON','S_E'),2:('D_NON',),3:('D_E','D_CITY')}[track_type.get()]:
                    raise ValueError('통신 단가 유형이 공통 선로형식과 일치하지 않습니다.')
                comm_codes=[f'COMM_ROUGH_{comm_key}_KM']
                if stations>0:comm_codes.append(f'COMM_ROUGH_{comm_key}_ST')
            if signal_code and not _eligible_for_track(signal_code,track_type.get()):
                raise ValueError('신호 단가가 공통 선로형식과 일치하지 않습니다.')
            arch_counts={}
            for v,c in arch_entries:
                code=lookup.get(v.get(),'')
                if not code:continue
                if not _eligible_for_track(code,track_type.get()):raise ValueError('건축 단가가 공통 선로형식과 일치하지 않습니다.')
                try:n=Decimal(c.get().strip())
                except Exception as exc:raise ValueError('건축 개소수는 0 이상의 정수여야 합니다.') from exc
                if not n.is_finite() or n<0 or n!=n.to_integral_value():raise ValueError('건축 개소수는 0 이상의 정수여야 합니다.')
                if n:arch_counts[code]=arch_counts.get(code,Decimal(0))+n
            has_roadbed=any(chosen.values()) or bool(classify_tunnels(editor.segments)[1]);has_system=any(system_chosen.values()) or any(power_chosen.values()) or any(cat_chosen.values()) or bool(signal_code) or bool(comm_codes) or trans_enabled.get() or sub_enabled.get() or bool(arch_counts)
            if not has_roadbed and not has_system:raise ValueError('최소 1개 개략 단가를 선택하세요.')
            rows=[];review=[];road_lengths={}
            if has_roadbed:
                width,cut,fill=(float(v.get()) for v in editor.earthwork_vars)
                earth=calculate_earthwork(read_ground_points(source),alignment,editor.segments,width,cut,fill)
                ordinary_tunnels,long_tunnels=classify_tunnels(editor.segments)
                if not long_tunnels:
                    rows,review,road_lengths=estimate_rough(earth,editor.segments,chosen,config=load_config())
                else:
                    # Keep frozen estimator untouched. It computes earth/bridge using all
                    # structures, while tunnel is handled separately per individual segment.
                    base_chosen=dict(chosen);base_chosen['터널']=''
                    rows,review,road_lengths=estimate_rough(earth,editor.segments,base_chosen,config=load_config())
                    review=[r for r in review if r[0]!='터널']
                    if ordinary_tunnels:
                        if chosen.get('터널'):
                            ordinary_rows,_,_=estimate_rough(earth,ordinary_tunnels,{'터널':chosen['터널']},config=load_config())
                            rows.extend(r for r in ordinary_rows if r.group=='터널')
                        else:
                            review.append(('터널',f'10km 미만 일반터널 {sum(s.length for s in ordinary_tunnels)/1000:.6f}km 단가 미선택'))
                    settings={key:({'shaft_mode':'individual','shaft_lengths_km':[v.get() for v in st['shafts']],'fire_percent':st['fire'].get()} if st['mode'].get()=='individual' else {'shaft_mode':'simple','shaft_length_km':st['length'].get(),'shaft_count':st['count'].get(),'fire_percent':st['fire'].get()}) for key,st in long_tunnel_entries.items()}
                    rows.extend(estimate_long_tunnels(long_tunnels,track_type.get(),settings))
            system_records=[];lengths=None
            if has_system:
                lengths=segment_lengths(alignment.vips,editor.segments)
                # Prevent selecting two power prices for same scope; group identifiers are internal.
                selections_to_calc=dict(system_chosen)
                for scope,code in power_chosen.items():
                    if code:selections_to_calc['전력_'+scope]=code
                for scope,code in cat_chosen.items():
                    if code:system_records+=_rough_system_rows(catalog,{'전차선':code},lengths,system_track_count())
                if trans_enabled.get():
                    km=lengths['전체']/Decimal(1000)
                    system_records+=_rough_system_rows(catalog,{'송전선로':select_transmission_band(km)},lengths,system_track_count())
                if sub_enabled.get():
                    km=lengths['전체']/Decimal(1000)
                    system_records+=_rough_system_rows(catalog,{'변전설비':select_substation_band(km,system_track_count())},lengths,system_track_count())
                for arch_code,arch_qty in arch_counts.items():
                    system_records+=_rough_system_rows(catalog,{'건축':arch_code},lengths,system_track_count(),arch_counts=arch_counts)
                if signal_code:
                    system_records+=_rough_system_rows(catalog,{'신호':signal_code},lengths,system_track_count())
                for comm_code in comm_codes:
                    system_records+=_rough_system_rows(catalog,{'통신':comm_code},lengths,system_track_count(),stations)
                for key,code in selections_to_calc.items():
                    group='전력' if key.startswith('전력_') else key
                    system_records+=_rough_system_rows(catalog,{group:code},lengths,system_track_count())
            path=filedialog.asksaveasfilename(parent=win,title='개략 공사비 XLSX 저장 (노반 D5 + 시스템 개략 별도 시트)',defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
            if not path:return
            # HF2: assemble the complete workbook in memory. No filesystem
            # temporary files, os.replace, or Windows rename/delete races.
            from io import BytesIO
            from openpyxl import load_workbook
            main = None
            system_wb = None
            buffer = None
            try:
                if has_roadbed:
                    buffer = BytesIO()
                    export_cost_xlsx(buffer, rows, review, road_lengths, load_config())
                    buffer.seek(0)
                    main = load_workbook(buffer)
                if has_system:
                    system_wb = _build_system_workbook(system_records, lengths, system_track_count())
                    if main is None:
                        main = system_wb
                        system_wb = None
                    else:
                        for src_ws in system_wb:
                            # Both source workbooks have '산정기준'; keep D5
                            # roadbed sheet unchanged, add system basis separately.
                            sheet_name = ('시스템산정기준' if src_ws.title == '산정기준'
                                          else src_ws.title)
                            dst_ws = main.create_sheet(sheet_name)
                            for cells in src_ws.iter_rows():
                                for cell in cells:
                                    dst_ws[cell.coordinate] = cell.value
                # A single openpyxl save writes directly to the selected path.
                # No .rough_cost_* files are created at any stage.
                main.save(path)
            except PermissionError as exc:
                raise PermissionError(
                    f'선택한 XLSX에 쓰기 권한이 없거나 다른 프로그램이 사용 중입니다: {path}\n'
                    'Excel/탐색기 미리보기/동기화 프로그램의 파일 점유 여부를 확인하세요.'
                ) from exc
            finally:
                if main is not None:
                    main.close()
                if system_wb is not None:
                    system_wb.close()
                if buffer is not None:
                    buffer.close()
            editor.log(f'개략 공사비 XLSX 저장(U7-LONGTUN1, 선로형식={track_type.get()}): {path}')
            status.set('저장 완료 · 노반은 기존 D5 형식, 시스템은 독립 시트로 산정 · 미선택 공종은 미산정')
            messagebox.showinfo('개략 공사비','XLSX 저장 완료. 시스템 개략 항목은 별도 시트로 출력됩니다. 기존 D5는 노반만 읽습니다.',parent=win)
        except (ValueError,TypeError,OSError,ImportError,KeyError) as exc:
            messagebox.showerror('개략 공사비',str(exc),parent=win)
    ttk.Button(footer,text='개략 공사비 XLSX 출력 (U7)',command=export).pack(side='right')
    ttk.Button(footer,text='닫기',command=win.destroy).pack(side='right',padx=10)
    return win
