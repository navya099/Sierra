"""v12.5.1 structure candidate editor; never modifies source DXF."""
from dataclasses import replace
from pathlib import Path
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from structure_engine import (StructureSettings, StructureSegment, detect_structures,
                              export_csv, load_manual_csv)
from profile_calculator import read_ground_points

class StructureEditor(ttk.Frame):
    def __init__(self, parent, get_context, log):
        super().__init__(parent)
        self.get_context = get_context  # returns (dxf_path, VerticalAlignment)
        self.log = log
        self.segments = []
        self.dirty = False
        self.settings_vars = [tk.StringVar(value=x) for x in ('40','100','15','100')]
        settings = ttk.LabelFrame(self, text='자동 판정 기준 (m)', padding=7)
        settings.pack(fill='x', padx=5, pady=4)
        for i,(label,var) in enumerate(zip(('터널 최대 절토고','터널 최소 길이','교량 최대 성토고','교량 최소 길이'),self.settings_vars)):
            ttk.Label(settings,text=label).grid(row=i//2,column=(i%2)*2,sticky='w',padx=4,pady=3)
            ttk.Entry(settings,textvariable=var,width=12).grid(row=i//2,column=(i%2)*2+1,padx=5,pady=3)
        actions=ttk.Frame(self); actions.pack(fill='x',padx=5,pady=4)
        for title,fn in [('자동 후보 생성',self.auto_generate),('추가',self.add),('수정',self.edit),('삭제',self.delete),('CSV 저장',self.save_csv),('CSV 불러오기',self.load_csv)]:
            ttk.Button(actions,text=title,command=fn).pack(side='left',padx=3)
        ttk.Label(self,text='자동 후보 생성은 현재 목록을 교체합니다. 수정 중인 내용은 먼저 CSV로 저장하세요.').pack(anchor='w',padx=8)
        cols=('유형','명칭','시작 STA','종료 STA','길이','최대고','최대고 STA','출처')
        wrap=ttk.Frame(self); wrap.pack(fill='both',expand=True,padx=5,pady=5)
        self.tree=ttk.Treeview(wrap,columns=cols,show='headings',selectmode='browse')
        for c in cols:
            self.tree.heading(c,text=c); self.tree.column(c,width=108,anchor='center',stretch=True)
        self.tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(wrap,orient='vertical',command=self.tree.yview)
        scroll.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<Double-1>',lambda e:self.edit())
        self.status=tk.StringVar(value='구조물 후보 없음')
        ttk.Label(self,textvariable=self.status).pack(anchor='w',padx=8,pady=4)

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,s in enumerate(self.segments):
            self.tree.insert('', 'end',iid=str(i),values=(s.kind,s.name,f'{s.start_sta:.3f}',f'{s.end_sta:.3f}',f'{s.length:.3f}',f'{s.max_height:.3f}',f'{s.peak_sta:.3f}',s.source))
        self.status.set(f'{len(self.segments)}개 구조물 · 터널 {sum(s.kind=="TUNNEL" for s in self.segments)}개 · 교량 {sum(s.kind=="BRIDGE" for s in self.segments)}개'+(' · 미저장' if self.dirty else ''))

    def _settings(self):
        return StructureSettings(*(float(v.get()) for v in self.settings_vars))

    def auto_generate(self):
        try:
            path, alignment = self.get_context()
            if not path or alignment is None: raise ValueError('먼저 종단 DXF를 불러오고 계산을 완료하세요.')
            settings=self._settings()
            generated=detect_structures(read_ground_points(path),alignment,settings)
        except (ValueError,TypeError,OSError) as exc:
            messagebox.showerror('구조물 자동 판정',str(exc),parent=self); return
        if self.segments and not messagebox.askyesno('후보 교체','기존 구조물 목록(수동 수정 포함)을 새 자동 판정 결과로 교체할까요?\n필요하면 먼저 CSV로 저장하세요.',parent=self): return
        self.segments=generated; self.dirty=True; self._refresh()
        self.log(f'구조물 자동 판정: {len(generated)}개 (현재 GUI 종곡선 설정 적용)')

    def _selected(self):
        sel=self.tree.selection()
        return int(sel[0]) if sel else None

    def _dialog(self, existing=None):
        dialog=tk.Toplevel(self); dialog.title('구조물 입력 / 수정'); dialog.transient(self.winfo_toplevel()); dialog.grab_set(); dialog.resizable(False,False)
        initial=existing or StructureSegment('BRIDGE',0,100,0,0,'MANUAL','')
        values=[tk.StringVar(value=v) for v in (initial.kind,initial.name,f'{initial.start_sta:g}',f'{initial.end_sta:g}')]
        for i,label in enumerate(('종류','명칭','시작 측점 (m)','종료 측점 (m)')):
            ttk.Label(dialog,text=label).grid(row=i,column=0,sticky='w',padx=12,pady=6)
            if i==0: ttk.Combobox(dialog,textvariable=values[i],values=('BRIDGE','TUNNEL'),state='readonly',width=23).grid(row=i,column=1,padx=12,pady=6)
            else: ttk.Entry(dialog,textvariable=values[i],width=26).grid(row=i,column=1,padx=12,pady=6)
        result=[]
        def accept():
            try:
                kind,name=values[0].get(),values[1].get().strip()
                a,b=float(values[2].get()),float(values[3].get())
                if kind not in ('BRIDGE','TUNNEL') or not all(map(math.isfinite,(a,b))) or a<0 or b<=a: raise ValueError('구조물 종류 및 측점 범위를 확인하세요.')
                path,alignment=self.get_context()
                if alignment and (a<alignment.vips[0][0]-1e-7 or b>alignment.vips[-1][0]+1e-7): raise ValueError('구조물 측점이 종단 범위를 벗어났습니다.')
                # Manual edits intentionally preserve the previously computed peak metadata.
                result.append(StructureSegment(kind,a,b,initial.max_height,initial.peak_sta,'MANUAL',name))
                dialog.destroy()
            except ValueError as exc: messagebox.showerror('입력 오류',str(exc),parent=dialog)
        ttk.Button(dialog,text='적용',command=accept).grid(row=4,column=0,columnspan=2,pady=12)
        dialog.wait_window()
        return result[0] if result else None

    def add(self):
        s=self._dialog()
        if s: self.segments.append(s);self.dirty=True;self._refresh()

    def edit(self):
        i=self._selected()
        if i is None: messagebox.showinfo('구조물','수정할 행을 선택하세요.',parent=self);return
        s=self._dialog(self.segments[i])
        if s: self.segments[i]=s;self.dirty=True;self._refresh()

    def delete(self):
        i=self._selected()
        if i is None:return
        if messagebox.askyesno('구조물 삭제','선택한 구조물을 삭제할까요?',parent=self):
            del self.segments[i];self.dirty=True;self._refresh()

    def save_csv(self):
        if not self.segments: messagebox.showinfo('구조물','저장할 구조물이 없습니다.',parent=self);return
        p=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',filetypes=[('CSV','*.csv')],initialfile='structure_segments.csv')
        if p:
            try: export_csv(self.segments,p)
            except OSError as exc: messagebox.showerror('CSV 저장 실패',str(exc),parent=self);return
            self.dirty=False;self._refresh();self.log(f'구조물 CSV 저장: {p}')

    def load_csv(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[('CSV','*.csv')])
        if not p:return
        try: segments=load_manual_csv(p)
        except (ValueError,KeyError,OSError) as exc: messagebox.showerror('CSV 불러오기 실패',str(exc),parent=self);return
        if self.dirty and not messagebox.askyesno('목록 교체','현재 미저장 목록을 교체할까요?',parent=self):return
        self.segments=segments;self.dirty=False;self._refresh();self.log(f'구조물 CSV 불러오기: {p}')

    def clear_for_new_project(self):
        if self.segments:
            self.segments=[];self.dirty=False;self._refresh()
