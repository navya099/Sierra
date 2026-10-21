"""U1: standalone rough-cost workspace; only verified roadbed calculations are enabled."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from cost_rough_engine import available_rough, estimate_rough, export_cost_xlsx
from quantity_price import load_config
from earthwork_simple import calculate_earthwork
from profile_calculator import read_ground_points

TABS = ('노반', '궤도', '전차선', '전력', '송전선로', '변전설비', '신호', '통신', '건축')


def open_rough_workspace(editor):
    win = tk.Toplevel(editor)
    win.title('v12.8-S2.5-U1 개략 공사비 계산')
    win.geometry('1060x650')
    win.minsize(850, 500)
    ttk.Label(win, text='KDI 개략 공사비 산정 | 개략 단가 전용 (세부 단가 사용 금지)', padding=10).pack(anchor='w')
    notebook = ttk.Notebook(win)
    notebook.pack(fill='both', expand=True, padx=10, pady=5)
    opts = available_rough()
    selections = {}
    lookup = {}
    for group in TABS:
        frame = ttk.Frame(notebook, padding=14)
        notebook.add(frame, text=group)
        if group != '노반':
            ttk.Label(frame, text=f'{group} 개략 공사비', font=('', 12, 'bold')).pack(anchor='w', pady=(0, 12))
            ttk.Label(frame, text='이 공종은 다음 단계에서 원문 개략 단가와 수량 연동을 검증한 뒤 활성화합니다.').pack(anchor='w')
            ttk.Label(frame, text='현재 버전에서는 산정하지 않으며, 0원으로 처리하지 않습니다.').pack(anchor='w', pady=8)
            continue
        ttk.Label(frame, text='노반 개략 공사비 | 기존 v12.7.2 토공·교량·터널 산정식 그대로 사용', font=('', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        ttk.Label(frame, text='단선·복선, 지역, 기초 조건은 자동 추정하지 않습니다. KDI 단가를 직접 선택하세요.').pack(anchor='w', pady=(0, 10))
        for work in ('토공', '교량', '터널'):
            row = ttk.Frame(frame, padding=6)
            row.pack(fill='x')
            ttk.Label(row, text=work, width=9).pack(side='left')
            choices = ['미선택 (미산정)']
            for item in opts[work]:
                label = f"{item['code']} | {item['spec']} | {item['condition']}"
                choices.append(label)
                lookup[label] = item['code']
            v = tk.StringVar(value=choices[0])
            selections[work] = v
            ttk.Combobox(row, textvariable=v, values=choices, state='readonly', width=95).pack(side='left', fill='x', expand=True)
        ttk.Label(frame, text='수량은 현재 선형·토공 계산 및 구조물 목록에서 산출합니다. 구조물 중첩은 기존 엔진에서 검증합니다.', wraplength=880).pack(anchor='w', pady=16)

    footer = ttk.Frame(win, padding=12)
    footer.pack(fill='x')
    status = tk.StringVar(value='노반 개략 산정 사용 가능 · 나머지 8개 공종은 구현 대기(미산정)')
    ttk.Label(footer, textvariable=status, wraplength=790).pack(anchor='w', pady=(0, 8))

    def export():
        try:
            source, alignment = editor.get_context()
            if not source or alignment is None:
                raise ValueError('먼저 종단 DXF를 불러오고 계산을 완료하세요.')
            width, cut, fill = (float(v.get()) for v in editor.earthwork_vars)
            earth = calculate_earthwork(read_ground_points(source), alignment, editor.segments, width, cut, fill)
            selected = {g: lookup.get(v.get(), '') for g, v in selections.items()}
            config = load_config()
            rows, review, lengths = estimate_rough(earth, editor.segments, selected, config=config)
            if not rows:
                raise ValueError('노반 탭에서 산정 가능한 개략 단가를 최소 1개 선택하세요.')
            path = filedialog.asksaveasfilename(parent=win, title='개략 공사비 XLSX 저장 (U1: 노반만 산정)', defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
            if not path:
                return
            # Keep v12.7.2 XLSX schema intact for the frozen D5 reader.
            export_cost_xlsx(path, rows, review, lengths, config)
            editor.log(f'개략 공사비 산정서 저장(U1, 노반): {path}')
            status.set('저장 완료: 노반 산정분만 포함. 기타 공종은 미산정이며 XLSX 범위 밖입니다.')
            messagebox.showinfo('개략 공사비', '저장 완료\n현재 U1에서는 노반만 산정합니다. 다른 공종은 미산정입니다.', parent=win)
        except (ValueError, TypeError, OSError, ImportError, KeyError) as exc:
            messagebox.showerror('개략 공사비', str(exc), parent=win)

    ttk.Button(footer, text='개략 공사비 XLSX 출력 (U1: 노반만)', command=export).pack(side='right')
    ttk.Button(footer, text='닫기', command=win.destroy).pack(side='right', padx=10)
    return win
