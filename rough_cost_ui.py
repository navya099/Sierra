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

TABS = ('노반','궤도','전차선','전력','송전선로','변전설비','신호','통신','건축')

def _source_catalog():
    return load_eligible_catalog(Path(__file__).with_name('kdi_general_rail_2019.json'))

def _rough_system_rows(catalog, selected, lengths, tracks):
    """Independent KDI rough-only records; never uses DETAIL rows."""
    lookup={r['code']:r for r in catalog}
    result=[]
    for group,code in selected.items():
        if not code:continue
        row=lookup.get(code)
        if row is None or row['group']!=group or row.get('method')!='ROUGH':
            raise ValueError(f'{group}: 개략 단가가 아닙니다: {code}')
        if row['unit']!='km':raise ValueError(f'{code}: km 단가만 지원합니다.')
        if group=='궤도':
            q=quantity_for_price(row,lengths,tracks,'전체')
            scope='전체'
        elif group=='전력':
            scope='터널' if code.endswith('_TUN') else '토공'
            expected=1 if code.startswith('POWER_S_') else 2
            if tracks!=expected:raise ValueError(f'{code}: 선택한 단선/복선 조건과 선로 수가 다릅니다.')
            q=lengths[scope]/Decimal(1000)
        else:raise ValueError(f'{group}: 아직 개략 계산을 지원하지 않습니다.')
        if q<=0:raise ValueError(f'{group}: {scope} 연장이 0km입니다.')
        price=Decimal(str(row['source_price_krw']))
        result.append({'group':group,'code':code,'name':row['name'], 'scope':scope,
                       'quantity':q,'unit':'km','unit_price':price,'amount':q*price,
                       'basis':provenance(row,'kdi_general_rail_2019.json')+f' | [U2 개략] {scope} {lengths[scope]}m / 1000'})
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
    note.append(['미산정 주의','미선택 공종과 전차선 개략표 Ⅲ-94는 0원으로 간주하지 않음'])
    note.append(['D5 호환','본 파일은 시스템 개략 보조 산정서이며 기존 D5 노반 입력 파일로 사용하지 않음'])
    for sheet in wb:
        sheet.freeze_panes='A2'
        for c in sheet[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='17365D')
        for col in 'ABCDEFGHI':sheet.column_dimensions[col].width=28 if col!='I' else 90
    return wb

def open_rough_workspace(editor):
    win=tk.Toplevel(editor);win.title('v12.8-S2.5-U2 개략 공사비 계산');win.geometry('1100x710');win.minsize(850,550)
    ttk.Label(win,text='KDI 개략 공사비 전용 | 세부 단가 사용 금지',padding=10).pack(anchor='w')
    notebook=ttk.Notebook(win);notebook.pack(fill='both',expand=True,padx=10,pady=5)
    opts=available_rough();catalog=_source_catalog();lookup={};selections={};system_vars={};power_vars={}
    track_count=tk.IntVar(value=1)
    def picker(parent,group,rows,variable):
        choices=['미선택 (미산정)']
        for item in rows:
            label=f"{item['code']} | {item.get('spec','')} | {item.get('condition','')} | {int(item['source_price_krw']):,}원/{item['unit']}"
            choices.append(label);lookup[label]=item['code']
        variable.set(choices[0]);ttk.Combobox(parent,textvariable=variable,values=choices,state='readonly',width=95).pack(fill='x',pady=5)
    for group in TABS:
        frame=ttk.Frame(notebook,padding=14);notebook.add(frame,text=group)
        ttk.Label(frame,text=group+' 개략 공사비',font=('',12,'bold')).pack(anchor='w',pady=(0,10))
        if group=='노반':
            ttk.Label(frame,text='기존 v12.7.2 노반 개략 계산식 및 D5 호환 XLSX 그대로 사용').pack(anchor='w')
            for work in ('토공','교량','터널'):
                row=ttk.Frame(frame,padding=5);row.pack(fill='x')
                ttk.Label(row,text=work,width=9).pack(side='left')
                choices=['미선택 (미산정)']
                for item in opts[work]:
                    label=f"{item['code']} | {item['spec']} | {item['condition']}";choices.append(label);lookup[label]=item['code']
                v=tk.StringVar(value=choices[0]);selections[work]=v
                ttk.Combobox(row,textvariable=v,values=choices,state='readonly',width=95).pack(side='left',fill='x',expand=True)
            ttk.Label(frame,text='토공·교량·터널 연장은 기존 검증된 노반 계산에서 산출합니다.',wraplength=850).pack(anchor='w',pady=15)
        elif group in ('궤도','전력'):
            ttk.Label(frame,text='선로수(공통): 단선 또는 복선 직접 선택').pack(anchor='w')
            ttk.Radiobutton(frame,text='단선',variable=track_count,value=1).pack(anchor='w')
            ttk.Radiobutton(frame,text='복선',variable=track_count,value=2).pack(anchor='w')
            rows=[r for r in catalog if r['group']==group and r.get('method')=='ROUGH']
            if group=='궤도':
                ttk.Label(frame,text='전체 노선연장 × 선택한 KDI 궤도 개략 km 단가 (1개 선택)').pack(anchor='w',pady=8)
                v=tk.StringVar();system_vars[group]=v;picker(frame,group,rows,v)
            else:
                ttk.Label(frame,text='토공과 터널은 각각 원문 개략 단가를 선택합니다. 교량 별도 단가는 원문 DB에 없으므로 미산정으로 표시합니다.',wraplength=870).pack(anchor='w',pady=8)
                for scope in ('토공','터널'):
                    ttk.Label(frame,text=scope+' 단가').pack(anchor='w',pady=(8,0))
                    v=tk.StringVar();power_vars[scope]=v
                    picker(frame,group,[r for r in rows if (r['code'].endswith('_TUN'))==(scope=='터널')],v)
                ttk.Label(frame,text='전력의 토공·터널은 각각 별도 산정하고, 구조물 연장 중복 적용을 방지합니다.').pack(anchor='w',pady=10)
        elif group=='전차선':
            ttk.Label(frame,text='원문 개략표 Ⅲ-94 단가가 아직 DB에 없습니다. 기존 CAT_* 항목은 세부표 Ⅲ-95이므로 사용하지 않습니다.',wraplength=900).pack(anchor='w')
            ttk.Label(frame,text='개략 단가 원문 숫자 확인 및 DB 등록 후 이 탭을 활성화합니다. 현재 미산정입니다.').pack(anchor='w',pady=10)
        else:
            ttk.Label(frame,text='원문 개략 항목·수량 산정 방식 검증 후 다음 버전에서 활성화합니다. 현재 미산정입니다.').pack(anchor='w')
    footer=ttk.Frame(win,padding=12);footer.pack(fill='x')
    status=tk.StringVar(value='노반·궤도·전력 개략 선택 가능 | 전차선 및 기타 공종 미산정')
    ttk.Label(footer,textvariable=status,wraplength=950).pack(anchor='w',pady=(0,8))
    def export():
        try:
            source,alignment=editor.get_context()
            if not source or alignment is None:raise ValueError('먼저 종단 DXF를 불러오고 계산을 완료하세요.')
            chosen={g:lookup.get(v.get(),'') for g,v in selections.items()}
            system_chosen={g:lookup.get(v.get(),'') for g,v in system_vars.items()}
            power_chosen={scope:lookup.get(v.get(),'') for scope,v in power_vars.items()}
            has_roadbed=any(chosen.values());has_system=any(system_chosen.values()) or any(power_chosen.values())
            if not has_roadbed and not has_system:raise ValueError('최소 1개 개략 단가를 선택하세요.')
            rows=[];review=[];road_lengths={}
            if has_roadbed:
                width,cut,fill=(float(v.get()) for v in editor.earthwork_vars)
                earth=calculate_earthwork(read_ground_points(source),alignment,editor.segments,width,cut,fill)
                rows,review,road_lengths=estimate_rough(earth,editor.segments,chosen,config=load_config())
            system_records=[];lengths=None
            if has_system:
                lengths=segment_lengths(alignment.vips,editor.segments)
                # Prevent selecting two power prices for same scope; group identifiers are internal.
                selections_to_calc=dict(system_chosen)
                for scope,code in power_chosen.items():
                    if code:selections_to_calc['전력_'+scope]=code
                for key,code in selections_to_calc.items():
                    group='전력' if key.startswith('전력_') else key
                    system_records+=_rough_system_rows(catalog,{group:code},lengths,track_count.get())
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
                    system_wb = _build_system_workbook(system_records, lengths, track_count.get())
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
            editor.log(f'개략 공사비 XLSX 저장(U2): {path}')
            status.set('저장 완료 · 노반은 기존 D5 형식, 시스템은 독립 시트로 산정 · 미선택 공종은 미산정')
            messagebox.showinfo('개략 공사비','XLSX 저장 완료. 시스템 개략 항목은 별도 시트로 출력됩니다. 기존 D5는 노반만 읽습니다.',parent=win)
        except (ValueError,TypeError,OSError,ImportError,KeyError) as exc:
            messagebox.showerror('개략 공사비',str(exc),parent=win)
    ttk.Button(footer,text='개략 공사비 XLSX 출력 (U2)',command=export).pack(side='right')
    ttk.Button(footer,text='닫기',command=win.destroy).pack(side='right',padx=10)
    return win
