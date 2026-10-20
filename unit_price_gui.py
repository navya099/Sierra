"""Simple Tkinter price override editor; immutable KDI source."""
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from quantity_price import load_catalog,load_config,save_config,export_unit_prices_xlsx,effective_price

def open_unit_price_editor(parent):
    catalog=load_catalog();config=load_config()
    win=tk.Toplevel(parent);win.title('v12.8-S2.2.1 통합 KDI 단가 관리');win.geometry('1120x650')
    top=ttk.Frame(win,padding=8);top.pack(fill='x')
    year=tk.StringVar(value=str(config['design_year']));factor=tk.StringVar(value=str(config.get('default_factor',1)))
    ttk.Label(top,text='설계 기준연도').pack(side='left');ttk.Entry(top,textvariable=year,width=8).pack(side='left',padx=5)
    ttk.Label(top,text='기본 보정계수').pack(side='left');ttk.Entry(top,textvariable=factor,width=10).pack(side='left',padx=5)
    ttk.Label(top,text='※ 1.0은 물가보정 미적용 / 미래 계수 자동생성 안 함').pack(side='left',padx=12)
    cols=('코드','공종','항목','규격','조건','단위','원본(원)','적용(원)','모드')
    frame=ttk.Frame(win);frame.pack(fill='both',expand=True,padx=8,pady=4)
    tree=ttk.Treeview(frame,columns=cols,show='headings')
    for c in cols:tree.heading(c,text=c);tree.column(c,width=110,stretch=True)
    tree.pack(side='left',fill='both',expand=True)
    sb=ttk.Scrollbar(frame,command=tree.yview);sb.pack(side='right',fill='y');tree.configure(yscrollcommand=sb.set)
    lookup={x['code']:x for x in catalog['items']}
    def sync_config():
        config['design_year']=int(year.get());config['default_factor']=float(factor.get())
        if config['design_year']<1900 or config['default_factor']<=0:raise ValueError('연도 또는 계수를 확인하세요.')
    def refresh():
        tree.delete(*tree.get_children())
        for x in catalog['items']:
            override=config.get('items',{}).get(x['code'],{})
            try:p=effective_price(x,config)
            except ValueError:p=None
            tree.insert('', 'end',iid=x['code'],values=(x['code'],x['group'],x['name'],x['spec'],x['condition'],x['unit'],x['source_price_krw'] if x['source_price_krw'] is not None else '미검증',round(p,2) if p is not None else '미검증',override.get('mode','factor')))
    def edit():
        selected=tree.selection()
        if not selected:return
        x=lookup[selected[0]]
        if x['source_price_krw'] is None:
            messagebox.showwarning('단가 미검증','원문 가격 검증 전에는 단가를 적용할 수 없습니다.',parent=win);return
        d=tk.Toplevel(win);d.title(x['code']);d.transient(win);d.grab_set()
        override=config.get('items',{}).get(x['code'],{})
        mode=tk.StringVar(value=override.get('mode','factor'));f=tk.StringVar(value=str(override.get('factor',config.get('default_factor',1))));p=tk.StringVar(value=str(override.get('unit_price','')))
        ttk.Label(d,text=f"{x['name']} {x['spec']} / 원본 {x['source_price_krw']:,}원/{x['unit']}").grid(row=0,column=0,columnspan=2,padx=12,pady=8)
        ttk.Radiobutton(d,text='보정계수',variable=mode,value='factor').grid(row=1,column=0);ttk.Entry(d,textvariable=f).grid(row=1,column=1)
        ttk.Radiobutton(d,text='직접입력(원)',variable=mode,value='manual').grid(row=2,column=0);ttk.Entry(d,textvariable=p).grid(row=2,column=1)
        def apply():
            try:
                record={'mode':mode.get()}
                if mode.get()=='factor':record['factor']=float(f.get())
                else:record['unit_price']=float(p.get())
                test=dict(config);test['items']=dict(config.get('items',{}));test['items'][x['code']]=record
                effective_price(x,test)
                config.setdefault('items',{})[x['code']]=record
                refresh();d.destroy()
            except ValueError as e:messagebox.showerror('입력 오류',str(e),parent=d)
        ttk.Button(d,text='적용',command=apply).grid(row=3,column=0,columnspan=2,pady=8)
    def save():
        try:sync_config();save_config(config);refresh();messagebox.showinfo('저장','unit_price_config.json 저장 완료',parent=win)
        except (ValueError,OSError) as e:messagebox.showerror('저장 실패',str(e),parent=win)
    def export():
        try:
            sync_config();p=filedialog.asksaveasfilename(parent=win,defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')],title='KDI 단가산출서')
            if p:export_unit_prices_xlsx(p,catalog,config);messagebox.showinfo('완료','단가산출서 저장 완료',parent=win)
        except (ValueError,OSError) as e:messagebox.showerror('산출 실패',str(e),parent=win)
    buttons=ttk.Frame(win,padding=8);buttons.pack(fill='x')
    def browse_shared_catalogue():
        from kdi_shared_picker import open_kdi_picker
        def select_row(row, _db_name):
            code=row['code']
            if code not in lookup:
                raise ValueError('현재 단가 관리자에 해당 코드가 없습니다.')
            tree.selection_set(code)
            tree.focus(code)
            tree.see(code)
        open_kdi_picker(win,select_row)
    ttk.Button(buttons,text='통합 KDI 단가 찾기',command=browse_shared_catalogue).pack(side='left',padx=4)
    ttk.Button(buttons,text='선택 단가 수정',command=edit).pack(side='left',padx=4)
    ttk.Button(buttons,text='설정 JSON 저장',command=save).pack(side='left',padx=4)
    ttk.Button(buttons,text='단가산출서 XLSX...',command=export).pack(side='left',padx=4)
    ttk.Button(buttons,text='닫기',command=win.destroy).pack(side='right',padx=4)
    tree.bind('<Double-1>',lambda event:edit())
    refresh();return win
