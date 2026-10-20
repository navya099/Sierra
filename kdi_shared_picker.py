"""Shared KDI catalogue browser used by UI-C1 and S2.2.1.

The source catalogue is read-only. No hidden price adjustments.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from quantity_price import load_catalog
from system_kdi_link import load_eligible_catalog


def open_kdi_picker(parent, on_select, groups=None, initial_group=None):
    """Select a validated source price. on_select(row, catalogue_filename)."""
    db_path = Path(__file__).with_name('kdi_general_rail_2019.json')
    try:
        if groups is None:
            data = load_catalog(db_path)
            entries = [r for r in data['items'] if r.get('source_price_krw') is not None]
        else:
            entries = [r for r in load_eligible_catalog(db_path) if r['group'] in groups]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        messagebox.showerror('KDI 단가 DB 오류', str(exc), parent=parent)
        return None
    if not entries:
        messagebox.showinfo('단가 없음', '선택 가능한 검증 단가가 없습니다.', parent=parent)
        return None
    popup = tk.Toplevel(parent)
    popup.title('KDI 통합 단가 선택 — v12.8-S2.2.1')
    popup.geometry('1110x600')
    popup.transient(parent)
    popup.grab_set()
    ttk.Label(popup, text='단일 KDI 2019 원문 DB · 원화환산단가 표시 · 보정 없음 · 단가 적용은 선택한 공사비 입력란에만 반영', padding=8).pack(anchor='w')
    controls = ttk.Frame(popup, padding=7)
    controls.pack(fill='x')
    groups_present = sorted({r['group'] for r in entries})
    group_var = tk.StringVar(value=initial_group if initial_group in groups_present else '전체')
    ttk.Label(controls, text='공종').pack(side='left')
    group_box = ttk.Combobox(controls, textvariable=group_var, values=['전체']+groups_present, width=15, state='readonly')
    group_box.pack(side='left', padx=5)
    ttk.Label(controls, text='검색').pack(side='left', padx=(14, 5))
    query_var = tk.StringVar()
    ttk.Entry(controls, textvariable=query_var, width=36).pack(side='left')
    cols = ('공종','코드','항목명','규격','조건','단위','원문단가(원)','연도','출처')
    frame = ttk.Frame(popup, padding=8)
    frame.pack(fill='both', expand=True)
    tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse')
    widths = (75,180,150,125,135,75,135,65,110)
    for col, width in zip(cols,widths):
        tree.heading(col, text=col)
        tree.column(col, width=width, minwidth=55)
    tree.pack(side='left',fill='both',expand=True)
    scrollbar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    scrollbar.pack(side='right',fill='y')
    tree.configure(yscrollcommand=scrollbar.set)
    lookup = {str(i): row for i,row in enumerate(entries)}
    def refresh(*_):
        tree.delete(*tree.get_children())
        term = query_var.get().strip().lower()
        for key,row in lookup.items():
            if group_var.get()!='전체' and row['group']!=group_var.get():continue
            if term and term not in ' '.join(str(row.get(k,'')) for k in ('code','group','name','spec','condition')).lower():continue
            tree.insert('','end',iid=key,values=(row['group'],row['code'],row['name'],row.get('spec',''),row.get('condition',''),row['unit'],row['source_price_krw'],row['source_year'],row['source_table']))
    group_box.bind('<<ComboboxSelected>>',refresh)
    query_var.trace_add('write',refresh)
    refresh()
    def select(*_):
        chosen = tree.selection()
        if not chosen:return
        row=lookup[chosen[0]]
        try:on_select(row,db_path.name)
        except (ValueError,TypeError,KeyError) as exc:
            messagebox.showerror('단가 적용 오류',str(exc),parent=popup)
            return
        popup.destroy()
    buttons=ttk.Frame(popup,padding=8);buttons.pack(fill='x')
    ttk.Button(buttons,text='선택한 단가 적용',command=select).pack(side='left')
    ttk.Button(buttons,text='취소',command=popup.destroy).pack(side='right')
    tree.bind('<Double-1>',select)
    return popup
