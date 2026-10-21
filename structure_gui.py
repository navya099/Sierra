"""v12.5.1 structure candidate editor; never modifies source DXF."""
from dataclasses import replace
from pathlib import Path
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from quantity_structure import calculate_structure_quantities, export_quantities_xlsx
from quantity_tunnel import calculate_tunnel_quantities, export_tunnel_xlsx
from quantity_bridge import calculate_bridge_quantities, export_bridge_xlsx
from quantity_integrated import export_integrated_xlsx
from earthwork_simple import calculate_earthwork, export_earthwork_xlsx
from structure_engine import (StructureSettings, StructureSegment, detect_structures,
                              export_csv, load_manual_csv)
from profile_calculator import read_ground_points
from bridge_girder import GirderSettings
from bridge_pier import PierSettings
from tunnel_profile import TunnelSettings
from tunnel_portal import PortalSettings
from tunnel_section import load_tunnel_section
from structure_label import LabelSettings
from structure_plan_label import PlanLabelSettings
from bridge_plan import BridgePlanSection
from bridge_section import load_bridge_section
from bridge_plan_pier import PlanPierSettings
from bridge_plan_abutment import read_template, DEFAULT_TEMPLATE

class StructureEditor(ttk.Frame):
    def __init__(self, parent, get_context, log):
        super().__init__(parent)
        self.get_context = get_context  # returns (dxf_path, VerticalAlignment)
        self.log = log
        self.segments = []
        self.dirty = False
        self.earthwork_vars=[tk.StringVar(value=v) for v in ("10.0","1.5","1.5")]
        self.settings_vars = [tk.StringVar(value=x) for x in ('40','100','15','100','5')]
        settings = ttk.LabelFrame(self, text='자동 판정 기준 (m)', padding=7)
        settings.pack(fill='x', padx=5, pady=4)
        for i,(label,var) in enumerate(zip(('터널 최대 절토고','터널 최소 길이','교량 최대 성토고','교량 최소 길이','교량 시작 성토고'),self.settings_vars)):
            ttk.Label(settings,text=label).grid(row=i//2,column=(i%2)*2,sticky='w',padx=4,pady=3)
            ttk.Entry(settings,textvariable=var,width=12).grid(row=i//2,column=(i%2)*2+1,padx=5,pady=3)
        # Bridge settings live in a separate window; variables remain on this editor
        # so existing output and automatic-detection methods are unchanged.
        self.girder_vars=[tk.StringVar(value=v) for v in ('2.0','30.0','0.0','2.0')]
        self.pier_vars=[tk.StringVar(value=v) for v in ('2.0','1.5','6.0','1.5','2.0')]
        self.bridge_color_vars=[tk.StringVar(value=v) for v in ('4','1','1')]
        self.plan_pier_vars=[tk.StringVar(value=v) for v in ("3.0","6.0","6.0","9.0","9.0")]
        self.plan_section_path=tk.StringVar(value="")
        self.plan_abutment_path=tk.StringVar(value="")
        self._plan_section_cache=None
        self.tunnel_vars=[tk.StringVar(value=v) for v in ('2.0','9.0','2.0','5')]
        self.portal_vars=[tk.StringVar(value=v) for v in ('1.0','20.0','1.5','6')]
        self.portal_width_var=tk.StringVar(value='6.0')
        self.portal_enabled=tk.BooleanVar(value=True)
        self.portal_mode=tk.StringVar(value='default')
        self.portal_custom_path=tk.StringVar(value='')
        self.portal_plan_mode=tk.StringVar(value='default')
        self.portal_plan_custom_path=tk.StringVar(value='')
        self.tunnel_cover_var=tk.StringVar(value='0.0')
        self.tunnel_lining_var=tk.StringVar(value='0.2')
        self.tunnel_section_mode=tk.StringVar(value='default')
        self.tunnel_section_path=tk.StringVar(value='')
        self._tunnel_window=None
        self._bridge_window=None
        self._label_window=None
        self.plan_label_enabled=tk.BooleanVar(value=True)
        self.plan_label_vars=[tk.StringVar(value=v) for v in ('15.0','3.0','STRUCTURE_LABEL_PLAN','1')]
        self.label_vars=[tk.StringVar(value=v) for v in ('STA.','3.0','1','3.0','PSC')]
        self.label_custom_prefix=tk.StringVar(value='서기(현)')
        buttons_settings=ttk.Frame(self); buttons_settings.pack(anchor='w',padx=8,pady=5)
        ttk.Button(buttons_settings,text='교량 설정...',command=self.open_bridge_settings).pack(side='left',padx=3)
        ttk.Button(buttons_settings,text='터널 설정...',command=self.open_tunnel_settings).pack(side='left',padx=3)
        ttk.Button(buttons_settings,text='구조물 주석 설정...',command=self.open_label_settings).pack(side='left',padx=3)
        ttk.Button(buttons_settings,text='평면 레이블 설정...',command=self.open_plan_label_settings).pack(side='left',padx=3)
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

    def tunnel_settings(self):
        offset,height,step,color=(v.get().strip() for v in self.tunnel_vars)
        section=None
        if self.tunnel_section_mode.get()=='dxf':
            if not self.tunnel_section_path.get().strip():
                raise ValueError('사용자 터널 단면 DXF를 선택하세요.')
            section=load_tunnel_section(self.tunnel_section_path.get())
        settings=TunnelSettings(float(offset),float(height),float(step),int(color),float(self.tunnel_lining_var.get()),section,
                                PortalSettings(float(self.portal_vars[0].get()),float(self.portal_vars[1].get()),
                                               float(self.portal_vars[2].get()),int(self.portal_vars[3].get()),
                                               self.portal_custom_path.get().strip() if self.portal_mode.get()=='dxf' else '',
                                               float(self.portal_width_var.get()),
                                               self.portal_plan_custom_path.get().strip() if self.portal_plan_mode.get()=='dxf' else '')
                                if self.portal_enabled.get() else None)
        settings.validate()
        return settings

    def open_tunnel_settings(self):
        if self._tunnel_window is not None and self._tunnel_window.winfo_exists():
            self._tunnel_window.lift()
            return
        window=tk.Toplevel(self)
        self._tunnel_window=window
        window.title('터널 본체 및 갱문 설정 · v12.5.5-D.2')
        window.transient(self.winfo_toplevel())
        window.resizable(False,False)
        frame=ttk.Frame(window,padding=12)
        frame.pack(fill='both',expand=True)
        for i,(label,var) in enumerate(zip(('계획선에서 하부 OFFSET (m)','터널 본체 높이 (m)','측점 샘플 간격 (m)','TUNNEL_BODY 색상 (ACI)'),self.tunnel_vars)):
            ttk.Label(frame,text=label).grid(row=i,column=0,sticky='w',padx=5,pady=5)
            ttk.Entry(frame,textvariable=var,width=14).grid(row=i,column=1,padx=5,pady=5)
        ttk.Label(frame,text='최소 토피고 (m)').grid(row=4,column=0,sticky='w',padx=5,pady=5)
        ttk.Entry(frame,textvariable=self.tunnel_cover_var,width=14).grid(row=4,column=1,padx=5,pady=5)
        ttk.Label(frame,text='라이닝 두께 (m)').grid(row=5,column=0,sticky='w',padx=5,pady=5)
        ttk.Entry(frame,textvariable=self.tunnel_lining_var,width=14).grid(row=5,column=1,padx=5,pady=5)
        ttk.Label(frame,text='단면 입력 방식').grid(row=6,column=0,sticky='w',padx=5,pady=5)
        ttk.Combobox(frame,textvariable=self.tunnel_section_mode,values=('default','dxf'),state='readonly',width=12).grid(row=6,column=1,padx=5,pady=5)
        ttk.Label(frame,text='단면 DXF 경로 (mm)').grid(row=7,column=0,sticky='w',padx=5,pady=5)
        path_row=ttk.Frame(frame)
        path_row.grid(row=7,column=1,sticky='w',padx=5,pady=5)
        ttk.Entry(path_row,textvariable=self.tunnel_section_path,width=26).pack(side='left')
        def browse_tunnel():
            path=filedialog.askopenfilename(parent=window,title='터널 표준 단면 DXF 선택',filetypes=[('DXF','*.dxf')])
            if path:
                self.tunnel_section_path.set(path)
                self.tunnel_section_mode.set('dxf')
        ttk.Button(path_row,text='찾기',command=browse_tunnel).pack(side='left',padx=3)
        ttk.Label(frame,text='DXF: (0,0)=계획선, TUNNEL_OUTER / TUNNEL_INNER 폐합 폴리라인').grid(row=8,column=0,columnspan=2,sticky='w',pady=5)
        ttk.Checkbutton(frame,text='종단 갱문 자동 생성',variable=self.portal_enabled).grid(row=9,column=0,columnspan=2,sticky='w',pady=5)
        for idx,(caption,var) in enumerate(zip(('SL_HEIGHT (m)','SL_LENGTH (m)','SLOPE (1 : 수평비)','갱문 색상 (ACI)'),self.portal_vars),start=10):
            ttk.Label(frame,text=caption).grid(row=idx,column=0,sticky='w',padx=5,pady=3)
            ttk.Entry(frame,textvariable=var,width=14).grid(row=idx,column=1,padx=5,pady=3)
        ttk.Label(frame,text='SL_WIDTH (평면 갱문 폭, m)').grid(row=18,column=0,sticky='w',padx=5,pady=3)
        ttk.Entry(frame,textvariable=self.portal_width_var,width=14).grid(row=18,column=1,padx=5,pady=3)
        ttk.Label(frame,text='평면 갱문 방식').grid(row=19,column=0,sticky='w',padx=5,pady=3)
        ttk.Combobox(frame,textvariable=self.portal_plan_mode,values=('default','dxf'),state='readonly',width=12).grid(row=19,column=1,padx=5,pady=3)
        ttk.Label(frame,text='평면 갱문 DXF (mm)').grid(row=20,column=0,sticky='w',padx=5,pady=3)
        plan_row=ttk.Frame(frame)
        plan_row.grid(row=20,column=1,sticky='w',padx=5,pady=3)
        ttk.Entry(plan_row,textvariable=self.portal_plan_custom_path,width=26).pack(side='left')
        def browse_plan_portal():
            path=filedialog.askopenfilename(parent=window,title='평면 갱문 DXF 선택',filetypes=[('DXF','*.dxf')])
            if path:
                self.portal_plan_custom_path.set(path)
                self.portal_plan_mode.set('dxf')
        ttk.Button(plan_row,text='찾기',command=browse_plan_portal).pack(side='left',padx=3)
        ttk.Label(frame,text='평면 DXF: 원점=(터널 시작/종료 중심선), +X=진행방향, +Y=좌측, mm').grid(row=21,column=0,columnspan=2,sticky='w',pady=3)
        ttk.Label(frame,text='DXF는 접선 방향 회전·평행이동만 적용, 곡선 변형 없음').grid(row=22,column=0,columnspan=2,sticky='w',pady=3)
        ttk.Label(frame,text='갱문 방식').grid(row=14,column=0,sticky='w',padx=5,pady=3)
        ttk.Combobox(frame,textvariable=self.portal_mode,values=('default','dxf'),state='readonly',width=12).grid(row=14,column=1,padx=5,pady=3)
        ttk.Label(frame,text='갱문 DXF 경로 (mm)').grid(row=15,column=0,sticky='w',padx=5,pady=3)
        portal_row=ttk.Frame(frame)
        portal_row.grid(row=15,column=1,sticky='w',padx=5,pady=3)
        ttk.Entry(portal_row,textvariable=self.portal_custom_path,width=26).pack(side='left')
        def browse_portal():
            path=filedialog.askopenfilename(parent=window,title='종단 갱문 DXF 선택',filetypes=[('DXF','*.dxf')])
            if path:
                self.portal_custom_path.set(path)
                self.portal_mode.set('dxf')
        ttk.Button(portal_row,text='찾기',command=browse_portal).pack(side='left',padx=3)
        ttk.Label(frame,text='사용자 갱문 DXF: 원점=(터널 계획선 STA·EL), mm, 시작부는 -X 방향').grid(row=16,column=0,columnspan=2,sticky='w',pady=4)
        ttk.Label(frame,text='사용자 DXF는 접속점 구배로 강체 회전 (종곡선 변형 없음)').grid(row=17,column=0,columnspan=2,sticky='w',pady=4)
        def apply():
            try:
                ts=self.tunnel_settings()
                cover=float(self.tunnel_cover_var.get())
                if not math.isfinite(cover) or cover < 0:
                    raise ValueError('최소 토피고는 0 이상의 유한한 숫자여야 합니다.')
                path,alignment=self.get_context()
                # A changed section must not silently overwrite manual stations.
                if self.segments and path and alignment is not None:
                    if not messagebox.askyesno('터널 범위 재계산',
                            '변경된 터널 높이/하부 OFFSET/토피고로 자동 구조물 범위를 재계산합니다.\n'
                            '수동 구조물은 유지하고 자동 구조물만 갱신할까요?',parent=window):
                        return
                    manual=[seg for seg in self.segments if seg.source != 'AUTO']
                    automatic=detect_structures(read_ground_points(path),alignment,self._settings())
                    self.segments=sorted(manual+automatic,key=lambda seg:seg.start_sta)
                    self.dirty=True
                    self._refresh()
                    self.log('터널 단면 변경: 자동 구조물 재판정 및 경계 갱신 완료 (수동 구조물 유지)')
            except (ValueError,TypeError,OSError) as exc:
                messagebox.showerror('터널 설정',str(exc),parent=window)
                return
            window.destroy()
        ttk.Button(frame,text='확인',command=apply).grid(row=23,column=1,sticky='e',pady=5)
        window.protocol('WM_DELETE_WINDOW',window.destroy)

    def open_bridge_settings(self):
        if self._bridge_window is not None and self._bridge_window.winfo_exists():
            self._bridge_window.lift()
            self._bridge_window.focus_set()
            return
        window=tk.Toplevel(self)
        self._bridge_window=window
        window.title('교량 설정 · v12.5.2-D')
        window.transient(self.winfo_toplevel())
        window.resizable(False,False)
        container=ttk.Frame(window,padding=12)
        container.pack(fill='both',expand=True)
        groups=(
            ('거더 설정', ('거더 높이 (m)','기준 경간 (m)','거더 상단 이격 (m)','샘플 간격 (m)'),self.girder_vars),
            ('교각 설정', ('교각 폭 (m)','코핑부 높이 (m)','기초 폭 (m)','기초 높이 (m)','기초 매입 깊이 (m)'),self.pier_vars),
            ('기타 설정 · 레이어 색상 (AutoCAD ACI 1~255)', ('거더 BRIDGE_GIRDER','교대 BRIDGE_ABUTMENT','교각 BRIDGE_PIER'),self.bridge_color_vars),
        )
        for heading,labels,variables in groups:
            frame=ttk.LabelFrame(container,text=heading,padding=8)
            frame.pack(fill='x',pady=4)
            for i,(label,var) in enumerate(zip(labels,variables)):
                ttk.Label(frame,text=label).grid(row=i//2,column=(i%2)*2,sticky='w',padx=4,pady=4)
                ttk.Entry(frame,textvariable=var,width=12).grid(row=i//2,column=(i%2)*2+1,padx=4,pady=4)
        section_frame=ttk.LabelFrame(container,text='평면 교량 단면 · v12.5.4-B',padding=8)
        section_frame.pack(fill='x',pady=4)
        ttk.Label(section_frame,text='미지정 시 내장 기본 단면 사용').grid(row=0,column=0,columnspan=3,sticky='w',pady=3)
        ttk.Entry(section_frame,textvariable=self.plan_section_path,width=48,state='readonly').grid(row=1,column=0,columnspan=2,sticky='ew',padx=3)
        def browse_section():
            path=filedialog.askopenfilename(parent=window,title='교량 표준 횡단면 DXF',filetypes=[('DXF 파일','*.dxf')])
            if not path:return
            try:
                section=load_bridge_section(path)
            except Exception as exc:
                messagebox.showerror('교량 단면 DXF 검증 실패',str(exc),parent=window);return
            self.plan_section_path.set(path)
            self._plan_section_cache=(path,section)
            section_status.set(f'슬래브 {section.slab_right-section.slab_left:.3f}m · 거더 {len(section.girders)}열')
        def reset_section():
            self.plan_section_path.set('');self._plan_section_cache=None
            section_status.set('내장 기본 단면 사용')
        ttk.Button(section_frame,text='DXF 불러오기...',command=browse_section).grid(row=1,column=2,padx=3)
        ttk.Button(section_frame,text='기본 단면 복원',command=reset_section).grid(row=2,column=2,padx=3,pady=4)
        section_status=tk.StringVar(value='내장 기본 단면 사용' if not self.plan_section_path.get() else '사용자 DXF 단면 선택됨')
        ttk.Label(section_frame,textvariable=section_status).grid(row=2,column=0,columnspan=2,sticky='w',padx=3)
        plan_pier_frame=ttk.LabelFrame(container,text="평면 교각 및 기초 (m) · v12.5.4-C",padding=7)
        plan_pier_frame.pack(fill="x",pady=5)
        for i,(label,var) in enumerate(zip(("기둥 지름","코핑 횡방향 폭","코핑 종방향 길이","기초 횡방향 폭","기초 종방향 길이"),self.plan_pier_vars)):
            ttk.Label(plan_pier_frame,text=label).grid(row=i,column=0,sticky="w",padx=5,pady=2)
            ttk.Entry(plan_pier_frame,textvariable=var,width=12).grid(row=i,column=1,padx=5,pady=2)
        abutment_frame=ttk.LabelFrame(container,text='평면 교대 DXF · v12.5.4-D',padding=8)
        abutment_frame.pack(fill='x',pady=4)
        ttk.Label(abutment_frame,text='기본값: 내장 교대일반도.dxf (mm, 원점 0,0)').grid(row=0,column=0,columnspan=3,sticky='w')
        ttk.Entry(abutment_frame,textvariable=self.plan_abutment_path,width=48,state='readonly').grid(row=1,column=0,columnspan=2,sticky='ew',padx=3)
        def browse_abutment():
            path=filedialog.askopenfilename(parent=window,title='교대 평면 형상 DXF',filetypes=[('DXF 파일','*.dxf')])
            if not path:return
            try: read_template(path)
            except Exception as exc:
                messagebox.showerror('교대 DXF 검증 실패',str(exc),parent=window);return
            self.plan_abutment_path.set(path)
        ttk.Button(abutment_frame,text='DXF 불러오기...',command=browse_abutment).grid(row=1,column=2,padx=3)
        ttk.Button(abutment_frame,text='내장 도면 복원',command=lambda:self.plan_abutment_path.set('')).grid(row=2,column=2,padx=3,pady=3)
        def apply():
            try:
                self.plan_pier_settings()
                read_template(self.bridge_abutment_plan_path())
                self.bridge_plan_section()
                self.girder_settings()
                self.pier_settings()
                self.bridge_layer_colors()
            except (ValueError,TypeError) as exc:
                messagebox.showerror('교량 설정',str(exc),parent=window)
                return
            window.destroy()
        buttons=ttk.Frame(container)
        buttons.pack(fill='x',pady=6)
        ttk.Button(buttons,text='확인',command=apply).pack(side='right',padx=4)
        ttk.Button(buttons,text='닫기',command=window.destroy).pack(side='right',padx=4)
        window.protocol('WM_DELETE_WINDOW',window.destroy)

    def bridge_abutment_plan_path(self):
        return self.plan_abutment_path.get().strip() or str(DEFAULT_TEMPLATE)

    def plan_pier_settings(self):
        settings=PlanPierSettings(*(float(v.get()) for v in self.plan_pier_vars))
        settings.validate()
        return settings

    def bridge_plan_section(self):
        path=self.plan_section_path.get().strip()
        if not path:
            return BridgePlanSection()
        # Revalidate from disk on every export; never use stale geometry after CAD edits.
        return load_bridge_section(path)

    def label_settings(self):
        prefix,height,color,margin,bridge_type=(v.get().strip() for v in self.label_vars)
        actual_prefix = 'STA.' if prefix == 'STA.' else self.label_custom_prefix.get().strip()
        settings=LabelSettings(actual_prefix,float(height),int(color),float(margin),bridge_type)
        settings.validate()
        return settings

    def plan_label_settings(self):
        if not self.plan_label_enabled.get(): return None
        offset,height,layer,color=(v.get().strip() for v in self.plan_label_vars)
        settings=PlanLabelSettings(float(offset),float(height),layer,int(color))
        settings.validate()
        return settings

    def open_plan_label_settings(self):
        win=tk.Toplevel(self)
        win.title('평면 구조물 레이블 설정 · v12.5.5-E.1')
        frame=ttk.Frame(win,padding=12);frame.pack(fill='both',expand=True)
        ttk.Checkbutton(frame,text='평면 구조물 레이블 출력',variable=self.plan_label_enabled).grid(row=0,column=0,columnspan=2,sticky='w',pady=4)
        for i,(caption,var) in enumerate(zip(('선형 이격거리 (m, +좌측 / -우측)','문자 높이 (m)','레이어','색상 (ACI)'),self.plan_label_vars),start=1):
            ttk.Label(frame,text=caption).grid(row=i,column=0,sticky='w',padx=4,pady=5)
            ttk.Entry(frame,textvariable=var,width=25).grid(row=i,column=1,sticky='w',padx=4,pady=5)
        ttk.Label(frame,text='기존 종단 레이블의 구조물 명칭·측점 표기 설정 공유').grid(row=5,column=0,columnspan=2,sticky='w',pady=5)
        def apply():
            try:self.plan_label_settings()
            except (ValueError,TypeError) as exc:
                messagebox.showerror('평면 레이블 설정',str(exc),parent=win);return
            win.destroy()
        ttk.Button(frame,text='확인',command=apply).grid(row=6,column=1,sticky='e',pady=6)

    def open_label_settings(self):
        if self._label_window is not None and self._label_window.winfo_exists():
            self._label_window.lift(); self._label_window.focus_set(); return
        win=tk.Toplevel(self); self._label_window=win
        win.title('구조물 공통 위치 라벨 설정 · v12.5.3')
        win.transient(self.winfo_toplevel()); win.resizable(False,False)
        frame=ttk.Frame(win,padding=14);frame.pack(fill='both',expand=True)
        labels=('측점 표기 방식','문자 높이','레이어 색상 (ACI)','사선 끝 여유','교량 형식')
        for i,(label,var) in enumerate(zip(labels,self.label_vars)):
            ttk.Label(frame,text=label).grid(row=i,column=0,sticky='w',padx=5,pady=6)
            if i==0:
                ttk.Combobox(frame,textvariable=var,values=('STA.','사용자 지정'),state='readonly',width=18).grid(row=i,column=1,padx=5,pady=6)
            else:
                ttk.Entry(frame,textvariable=var,width=21).grid(row=i,column=1,padx=5,pady=6)
        ttk.Label(frame,text='사용자 지정 접두어').grid(row=5,column=0,sticky='w',padx=5,pady=6)
        prefix_entry=ttk.Entry(frame,textvariable=self.label_custom_prefix,width=21)
        prefix_entry.grid(row=5,column=1,padx=5,pady=6)
        def sync_prefix(*_):
            prefix_entry.configure(state='normal' if self.label_vars[0].get() != 'STA.' else 'disabled')
        self.label_vars[0].trace_add('write',sync_prefix)
        sync_prefix()
        ttk.Label(frame,text='예: 서기(현), 서기(환), 수기(환), 량기(현)').grid(row=6,column=0,columnspan=2,pady=3)
        ttk.Label(frame,text='수직선 30 · 사선 30° · 문자 회전 30° 고정').grid(row=7,column=0,columnspan=2,pady=7)
        def apply():
            try:self.label_settings()
            except (ValueError,TypeError) as exc:
                messagebox.showerror('주석 설정',str(exc),parent=win);return
            win.destroy()
        ttk.Button(frame,text='확인',command=apply).grid(row=8,column=1,sticky='e',pady=7)
        win.protocol('WM_DELETE_WINDOW',win.destroy)

    def bridge_layer_colors(self):
        names=('BRIDGE_GIRDER','BRIDGE_ABUTMENT','BRIDGE_PIER')
        colors={}
        for name,var in zip(names,self.bridge_color_vars):
            value=var.get().strip()
            if not value.isdecimal() or not 1<=int(value)<=255:
                raise ValueError(f'{name} 색상은 ACI 정수 1~255로 입력하세요.')
            colors[name]=int(value)
        return colors

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,s in enumerate(self.segments):
            self.tree.insert('', 'end',iid=str(i),values=(s.kind,s.name,f'{s.start_sta:.3f}',f'{s.end_sta:.3f}',f'{s.length:.3f}',f'{s.max_height:.3f}',f'{s.peak_sta:.3f}',s.source))
        self.status.set(f'{len(self.segments)}개 구조물 · 터널 {sum(s.kind=="TUNNEL" for s in self.segments)}개 · 교량 {sum(s.kind=="BRIDGE" for s in self.segments)}개'+(' · 미저장' if self.dirty else ''))

    def _settings(self):
        tunnel=self.tunnel_settings()
        return StructureSettings(*(float(v.get()) for v in self.settings_vars),
                                 float(self.girder_vars[0].get()) + float(self.girder_vars[2].get()),
                                 tunnel.section.body_height if tunnel.section else tunnel.body_height,
                                 tunnel.section.bottom_offset if tunnel.section else tunnel.bottom_offset,
                                 float(self.tunnel_cover_var.get()))

    def girder_settings(self):
        settings = GirderSettings(*(float(v.get()) for v in self.girder_vars))
        settings.validate()
        return settings

    def pier_settings(self):
        settings=PierSettings(*(float(v.get()) for v in self.pier_vars))
        settings.validate()
        return settings

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

    def open_earthwork_dialog(self):
        win=tk.Toplevel(self)
        win.title('v12.6.2 개략 토공량 — 수평 지반 가정')
        win.transient(self.winfo_toplevel())
        win.resizable(False,False)
        frame=ttk.Frame(win,padding=12);frame.pack(fill='both',expand=True)
        for i,(label,var) in enumerate(zip(('노반 폭 B (m)','절토 사면 (1:m)','성토 사면 (1:m)'),self.earthwork_vars)):
            ttk.Label(frame,text=label).grid(row=i,column=0,sticky='w',padx=5,pady=5)
            ttk.Entry(frame,textvariable=var,width=14).grid(row=i,column=1,padx=5,pady=5)
        ttk.Label(frame,text='지반은 횡방향 수평 가정 / 25m 기본 측점 / 구조물 구간 제외').grid(row=3,column=0,columnspan=2,pady=8)
        def save():
            try:
                width,cut,fill=(float(v.get()) for v in self.earthwork_vars)
                source,alignment=self.get_context()
                if not source or alignment is None:raise ValueError('먼저 종단 DXF를 불러오고 계산을 완료하세요.')
                result=calculate_earthwork(read_ground_points(source),alignment,self.segments,
                                           width,cut,fill)
                path=filedialog.asksaveasfilename(parent=win,title='개략 토공량 XLSX 저장',
                        defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
                if not path:return
                export_earthwork_xlsx(result,path)
                self.log(f'개략 토공량: 절토 {result.cut_m3:,.2f}m³, 성토 {result.fill_m3:,.2f}m³, 구조물 제외 {result.excluded_length_m:,.2f}m → {path}')
                messagebox.showinfo('개략 토공량','XLSX 수량산출서 저장 완료\n'
                    f'절토 {result.cut_m3:,.2f}m³ / 성토 {result.fill_m3:,.2f}m³',parent=win)
                win.destroy()
            except (ValueError,TypeError,OSError,ImportError) as exc:
                messagebox.showerror('개략 토공량',str(exc),parent=win)
        ttk.Button(frame,text='XLSX 산출...',command=save).grid(row=4,column=0,pady=8)
        ttk.Button(frame,text='취소',command=win.destroy).grid(row=4,column=1,pady=8)

    def open_unit_price_manager(self):
        from unit_price_gui import open_unit_price_editor
        open_unit_price_editor(self)

    def open_detail_cost_dialog(self):
        """Manual, auditable quantity input; v12.6.5 quantity engines remain untouched."""
        from cost_detail import available_detail,estimate_detail,export_detail_xlsx
        from quantity_price import load_config
        import json
        options=available_detail()
        lookup={x['code']:x for x in options}
        win=tk.Toplevel(self);win.title('v12.7.3-D4 세부 공사비 산정 (일괄 연동/NATM 분할)');win.geometry('1030x650')
        ttk.Label(win,text='KDI 세부 단가 선택 → 수량·근거 입력 → 항목 추가. 단위는 단가 DB 기준이며 자동 수량 추정은 하지 않습니다.',padding=8).pack(anchor='w')
        ttk.Label(win,text='같은 공종의 개략 공사비와 합산 금지. 교량 상부공(m)·하부공(개소), 터널 패턴(m) 등은 실제 설계 조건 확인 필수.',padding=8).pack(anchor='w')
        frame=ttk.Frame(win,padding=8);frame.pack(fill='x')
        values=[f"{x['code']} | {x['group']} | {x['name']} | {x['spec']} | {x['unit']}" for x in options]
        code_var=tk.StringVar(value=values[0] if values else '')
        ttk.Combobox(frame,textvariable=code_var,values=values,state='readonly',width=78).grid(row=0,column=0,columnspan=4,sticky='ew',pady=4)
        q_var=tk.StringVar();remark_var=tk.StringVar()
        ttk.Label(frame,text='수량').grid(row=1,column=0,sticky='e');ttk.Entry(frame,textvariable=q_var,width=17).grid(row=1,column=1,sticky='w')
        ttk.Label(frame,text='수량 근거').grid(row=1,column=2,sticky='e');ttk.Entry(frame,textvariable=remark_var,width=47).grid(row=1,column=3,sticky='ew')
        frame.columnconfigure(3,weight=1)
        columns=('코드','공종','수량','단위','수량 근거')
        tree=ttk.Treeview(win,columns=columns,show='headings',height=15)
        for col,width in zip(columns,(170,90,120,100,460)):
            tree.heading(col,text=col);tree.column(col,width=width,anchor='w')
        tree.pack(fill='both',expand=True,padx=10,pady=8)
        entries=[]
        def refresh():
            for iid in tree.get_children():tree.delete(iid)
            for i,e in enumerate(entries):
                item=lookup[e['code']]
                tree.insert('', 'end',iid=str(i),values=(e['code'],item['group'],e['quantity'],item['unit'],e['remark']))
        def add():
            try:
                code=code_var.get().split(' | ',1)[0]
                if code not in lookup:raise ValueError('세부 단가를 선택하세요.')
                q=float(q_var.get())
                if not math.isfinite(q) or q<=0:raise ValueError('수량은 0보다 큰 유한수여야 합니다.')
                entries.append({'code':code,'quantity':q,'remark':remark_var.get()})
                refresh();q_var.set('');remark_var.set('')
            except ValueError as exc:messagebox.showerror('수량 입력',str(exc),parent=win)
        def remove():
            ids=tree.selection()
            if ids:
                entries.pop(int(ids[0]));refresh()
        def export():
            try:
                if not entries:raise ValueError('산정할 세부 항목을 추가하세요.')
                config=load_config();rows=estimate_detail(entries,config=config)
                path=filedialog.asksaveasfilename(parent=win,title='세부 공사비 산정서 저장',defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
                if not path:return
                export_detail_xlsx(path,rows,config)
                self.log(f'세부 공사비 산정서 저장: {path}')
                messagebox.showinfo('세부 공사비',f'저장 완료: {len(rows)}개 항목\n산정분 합계만 표시됩니다.',parent=win)
            except (ValueError,TypeError,OSError,ImportError) as exc:messagebox.showerror('세부 공사비',str(exc),parent=win)
        def import_integrated():
            from quantity_detail_link import read_candidates,review_selection
            from quantity_price import load_catalog
            path=filedialog.askopenfilename(parent=win,title='v12.6.5 통합 수량산출서 선택',filetypes=[('Excel','*.xlsx')])
            if not path:return
            try:candidates=read_candidates(path)
            except (ValueError,OSError,KeyError,ImportError) as exc:
                messagebox.showerror('통합 수량 불러오기',str(exc),parent=win);return
            if not candidates:
                messagebox.showinfo('통합 수량 불러오기','연결 후보 수량이 없습니다.',parent=win);return
            review=tk.Toplevel(win);review.title('통합 수량 → KDI 세부 단가 연결 검토');review.geometry('1120x610')
            ttk.Label(review,text='수량은 자동 불러오지만 단가는 자동 확정하지 않습니다. 후보를 선택하고 실제 설계조건에 맞는 코드를 직접 선택하세요.',padding=8).pack(anchor='w')
            ttk.Label(review,text='터널 NATM 패턴별 분할·교량 기초형식·토질은 통합 수량산출서에 없으므로 반드시 별도 검토하세요.',padding=8).pack(anchor='w')
            cols=('공종','후보 수량','수량','단위','검토 사항')
            cand_tree=ttk.Treeview(review,columns=cols,show='headings',height=13)
            for c,w in zip(cols,(80,230,100,65,560)):
                cand_tree.heading(c,text=c);cand_tree.column(c,width=w,anchor='w')
            cand_tree.pack(fill='both',expand=True,padx=8,pady=8)
            for i,c in enumerate(candidates):
                cand_tree.insert('','end',iid=str(i),values=(c.group,c.item,f'{c.quantity:,.3f}',c.unit,c.warning))
            row=ttk.Frame(review,padding=8);row.pack(fill='x')
            ttk.Label(row,text='선택 후보에 적용할 세부 단가:').pack(side='left')
            match_var=tk.StringVar();combo=ttk.Combobox(row,textvariable=match_var,width=80,state='readonly');combo.pack(side='left',padx=8,fill='x',expand=True)
            cand_tree.configure(selectmode='extended')
            def compatible_codes(c):
                matches=[x for x in options if x['code'] in c.suggested_codes]
                if c.group=='교량':
                    if c.item.endswith(' 상부공'):
                        matches=[x for x in matches if x['code'].startswith('BRIDGE_DETAIL_SUPER_')]
                    elif c.item.endswith(' 교대'):
                        matches=[x for x in matches if x['code'].startswith('BRIDGE_DETAIL_SUB_') and '/ 교대 /' in x.get('spec','')]
                    elif c.item.endswith(' 교각'):
                        matches=[x for x in matches if x['code'].startswith('BRIDGE_DETAIL_SUB_') and '/ 교각 /' in x.get('spec','')]
                elif c.group=='터널' and 'NATM 미분류' in c.item:
                    # D3 does not allow an unallocated full tunnel length to be priced as one pattern.
                    return []
                return matches
            def choose(_=None):
                selected=cand_tree.selection()
                if not selected:return
                selected_candidates=[candidates[int(i)] for i in selected]
                compatible=compatible_codes(selected_candidates[0])
                for c in selected_candidates[1:]:
                    allowed={x['code'] for x in compatible_codes(c)}
                    compatible=[x for x in compatible if x['code'] in allowed]
                combo['values']=[f"{x['code']} | {x['name']} | {x['spec']} | {x['condition']} | {x['unit']}" for x in compatible]
                match_var.set('')
            cand_tree.bind('<<TreeviewSelect>>',choose)
            def transfer():
                try:
                    selected=cand_tree.selection()
                    if not selected:raise ValueError('수량 후보를 선택하세요.')
                    code=match_var.get().split(' | ',1)[0]
                    if not code:raise ValueError('선택한 후보에 공통으로 적용할 세부 단가를 선택하세요. 터널 NATM 미분류 연장은 패턴 분할 후 입력해야 합니다.')
                    prepared=[]
                    seen={e.get('source_id') for e in entries if e.get('source_id')}
                    for idx in selected:
                        c=candidates[int(idx)]
                        if code not in {x['code'] for x in compatible_codes(c)}:
                            raise ValueError(f'{c.item}: 선택 단가가 공종·구조물 유형에 맞지 않습니다.')
                        e=review_selection(c,code)
                        e['source_id']=str(path)+'::'+c.source
                        if e['source_id'] in seen:raise ValueError(f'{c.item}: 이미 추가한 수량 후보입니다.')
                        seen.add(e['source_id']);prepared.append((idx,c,e))
                    count=len(prepared);qty=sum(c.quantity for _,c,_ in prepared)
                    sample='\n'.join(f'  {c.item}: {c.quantity:g} {c.unit}' for _,c,_ in prepared[:8])
                    if count>8:sample+=f'\n  외 {count-8}개'
                    if not messagebox.askyesno('일괄 단가 적용 확인',
                        f'{count}개 후보 / 수량 합계 {qty:g} {prepared[0][1].unit}\n단가: {code}\n\n{sample}\n\n각 구조물의 형식·경간·단복선·기초조건이 모두 일치합니까?',parent=review):return
                    entries.extend(e for _,_,e in prepared);refresh()
                    for idx,_,_ in prepared:cand_tree.delete(idx)
                    match_var.set('')
                except (ValueError,TypeError) as exc:messagebox.showerror('단가 연결',str(exc),parent=review)
            def split_natm():
                from natm_pattern import allocate_natm,pattern_codes
                selected=cand_tree.selection()
                if len(selected)!=1:
                    messagebox.showerror('NATM 패턴 분할','터널 후보 1개만 선택하세요.',parent=review);return
                idx=selected[0];c=candidates[int(idx)]
                if c.group!='터널' or 'NATM 미분류 전체연장' not in c.item:
                    messagebox.showerror('NATM 패턴 분할','NATM 미분류 전체연장 후보를 선택하세요.',parent=review);return
                dialog=tk.Toplevel(review);dialog.title('NATM 패턴별 연장 배분 — '+c.item);dialog.geometry('760x455')
                ttk.Label(dialog,text=f'{c.item} | 총연장 {c.quantity:,.3f} m',padding=8).pack(anchor='w')
                ttk.Label(dialog,text='패턴별 실제 설계 연장(m)을 입력하세요. 0은 미적용이며 합계는 총연장과 일치해야 합니다.',padding=8).pack(anchor='w')
                codes=pattern_codes();grid=ttk.Frame(dialog,padding=8);grid.pack(fill='x')
                inputs=[]
                for n in range(1,7):
                    opts=[x for x in options if x['code'] in codes and x['code'].startswith(f'TUNNEL_DETAIL_MAIN_P{n}_')]
                    ttk.Label(grid,text=f'패턴 {n}').grid(row=n-1,column=0,padx=6,pady=5)
                    labels=[f"{x['code']} | {x['spec']}" for x in opts]
                    code_v=tk.StringVar(value=labels[0] if labels else '')
                    ttk.Combobox(grid,textvariable=code_v,values=labels,state='readonly',width=49).grid(row=n-1,column=1,padx=6)
                    length_v=tk.StringVar(value='0')
                    ttk.Entry(grid,textvariable=length_v,width=16).grid(row=n-1,column=2,padx=6)
                    ttk.Label(grid,text='m').grid(row=n-1,column=3)
                    inputs.append((code_v,length_v))
                total_var=tk.StringVar(value='입력 합계: 0.000 m')
                ttk.Label(dialog,textvariable=total_var,padding=8).pack(anchor='w')
                def recalc(*_):
                    try:
                        q=sum(float(v.get() or '0') for _,v in inputs)
                        total_var.set(f'입력 합계: {q:,.3f} m / 차이: {q-c.quantity:+,.3f} m')
                    except ValueError:total_var.set('숫자가 아닌 연장이 있습니다.')
                for _,v in inputs:v.trace_add('write',recalc)
                def commit():
                    try:
                        allocations=[(cv.get().split(' | ',1)[0],lv.get()) for cv,lv in inputs]
                        prepared=allocate_natm(c,allocations,path)
                        existing={e.get('source_id') for e in entries if e.get('source_id')}
                        if any(e['source_id'] in existing for e in prepared):
                            raise ValueError('이 터널의 패턴 수량이 이미 등록되어 있습니다.')
                        detail='\n'.join(f"{e['code']}: {e['quantity']:g}m" for e in prepared)
                        if not messagebox.askyesno('NATM 패턴 분할 확정',
                            f'{c.item} / 총연장 {c.quantity:g}m\n\n{detail}\n\n실제 설계 패턴 배분을 확인했습니까?',parent=dialog):return
                        entries.extend(prepared);refresh();cand_tree.delete(idx);match_var.set('');dialog.destroy()
                    except (ValueError,TypeError) as exc:messagebox.showerror('NATM 패턴 분할',str(exc),parent=dialog)
                ttk.Button(dialog,text='합계 검증 후 산정 항목 추가...',command=commit).pack(pady=8)
            ttk.Button(row,text='선택 터널 NATM 패턴 분할...',command=split_natm).pack(side='left',padx=5)
            ttk.Label(row,text='Ctrl/Shift 다중 선택 가능').pack(side='left',padx=5)
            ttk.Button(row,text='선택 후보 일괄 추가...',command=transfer).pack(side='right')
        buttons=ttk.Frame(win,padding=8);buttons.pack(fill='x')
        ttk.Button(buttons,text='통합 수량산출서 불러오기 / 단가 연결 검토...',command=import_integrated).pack(side='left',padx=5)

        ttk.Button(buttons,text='항목 추가',command=add).pack(side='left',padx=5)
        ttk.Button(buttons,text='선택 항목 삭제',command=remove).pack(side='left',padx=5)
        ttk.Button(buttons,text='세부 공사비 XLSX 산출...',command=export).pack(side='right',padx=5)

    def open_nonconstruction_cost_dialog(self):
        """T1: manually entered non-construction costs, isolated from D5."""
        from nonconstruction_cost import (
            CATEGORIES, DEFAULT_ITEMS, CostItem, parse_amount,
            validate, summarize, save_json, load_json, export_xlsx
        )
        win = tk.Toplevel(self)
        win.title('v12.7.4-T2 공사비 외 비용 산정')
        win.geometry('1020x610')
        win.transient(self.winfo_toplevel())
        ttk.Label(win, text='공사비 외 비용 직접 입력 (원). D5 공사비와 합산하지 않습니다.',
                  padding=8).pack(anchor='w')
        columns = ('분류', '항목명', '금액(원)', '산정 근거', '비고')
        tree = ttk.Treeview(win, columns=columns, show='headings', height=11)
        widths = (120, 180, 140, 290, 200)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor='e' if col == '금액(원)' else 'w')
        tree.pack(fill='both', expand=True, padx=10, pady=5)
        editor = ttk.LabelFrame(win, text='항목 입력 / 선택 행 수정', padding=8)
        editor.pack(fill='x', padx=10)
        cat = tk.StringVar(value=CATEGORIES[0])
        name = tk.StringVar()
        amount = tk.StringVar(value='0')
        basis = tk.StringVar()
        note = tk.StringVar()
        for idx, (label, var) in enumerate((('분류', cat), ('항목명', name), ('금액(원)', amount),
                                            ('산정 근거', basis), ('비고', note))):
            ttk.Label(editor, text=label).grid(row=0, column=idx, sticky='w')
            if idx == 0:
                ttk.Combobox(editor, textvariable=var, values=CATEGORIES,
                             state='readonly', width=14).grid(row=1, column=idx, padx=3, sticky='ew')
            else:
                ttk.Entry(editor, textvariable=var, width=(36 if idx == 3 else 19)).grid(
                    row=1, column=idx, padx=3, sticky='ew')
            editor.columnconfigure(idx, weight=2 if idx == 3 else 1)
        selected_id = [None]
        def pick(_event=None):
            ids = tree.selection()
            if not ids: return
            selected_id[0] = ids[0]
            values = tree.item(ids[0], 'values')
            for var, value in zip((cat, name, amount, basis, note), values):
                var.set(value)
        tree.bind('<<TreeviewSelect>>', pick)
        def read_all():
            return validate([
                CostItem(v[0], v[1], parse_amount(v[2]), v[3], v[4])
                for v in (tree.item(i, 'values') for i in tree.get_children())
            ])
        def refresh():
            try:
                totals = summarize(read_all())
                total_var.set('  |  '.join(f'{k}: {int(v):,}원' for k,v in totals.items())
                              + f'  |  합계: {int(sum(totals.values())):,}원')
            except ValueError as exc:
                total_var.set(str(exc))
        def apply():
            try:
                item = CostItem(cat.get(), name.get(), parse_amount(amount.get()),
                                basis.get(), note.get())
                values = (item.category, item.name.strip(), str(item.amount), item.basis, item.note)
                rows = [CostItem(*(tree.item(i,'values')[:2]),
                                 parse_amount(tree.item(i,'values')[2]),
                                 *tree.item(i,'values')[3:]) for i in tree.get_children()
                        if i != selected_id[0]]
                validate(rows + [item])
                if selected_id[0] and tree.exists(selected_id[0]):
                    tree.item(selected_id[0], values=values)
                else:
                    tree.insert('', 'end', values=values)
                selected_id[0] = None
                tree.selection_remove(tree.selection())
                refresh()
            except (ValueError,TypeError) as exc:
                messagebox.showerror('항목 검증', str(exc), parent=win)
        def delete():
            for item_id in tree.selection(): tree.delete(item_id)
            selected_id[0] = None
            refresh()
        def clear_selection():
            selected_id[0] = None
            tree.selection_remove(tree.selection())
            name.set(''); amount.set('0'); basis.set(''); note.set('')
        actions = ttk.Frame(win, padding=6)
        actions.pack(fill='x')
        def auto_calculate():
            """Write the calculation into the existing T1 editor, without saving until Apply."""
            from nonconstruction_auto import calculate, calculation_basis
            dialog=tk.Toplevel(win)
            dialog.title('T2 요율 자동 산정')
            dialog.geometry('650x360')
            dialog.transient(win)
            dialog.grab_set()
            ttk.Label(dialog,text='입력한 기준금액과 요율로 계산합니다. 공식 요율은 제공하지 않습니다.',
                      padding=8).pack(anchor='w')
            form=ttk.Frame(dialog,padding=10);form.pack(fill='x')
            base=tk.StringVar(value='0')
            rate=tk.StringVar(value='0')
            source=tk.StringVar(value='')
            rule=tk.StringVar(value='')
            for r,(label,var) in enumerate((('기준금액 (원)',base),('적용 요율 (%)',rate),
                                           ('기준금액 출처',source),('요율 적용 근거',rule))):
                ttk.Label(form,text=label,width=19).grid(row=r,column=0,sticky='w',pady=5)
                ttk.Entry(form,textvariable=var,width=55).grid(row=r,column=1,sticky='ew',pady=5)
            form.columnconfigure(1,weight=1)
            result=tk.StringVar(value='산정 결과: -')
            ttk.Label(dialog,textvariable=result,padding=8).pack(anchor='w')
            computed=[None]
            def preview():
                try:
                    value,pct=calculate(base.get(),rate.get())
                    basis_text=calculation_basis(parse_amount(base.get()),pct,source.get(),rule.get())
                    computed[0]=(value,basis_text)
                    result.set(f'산정 결과: {int(value):,}원 (원 단위 반올림)')
                except (ValueError,TypeError) as exc:
                    computed[0]=None
                    messagebox.showerror('자동 산정 오류',str(exc),parent=dialog)
            def transfer():
                preview()
                if computed[0] is None:return
                value,basis_text=computed[0]
                amount.set(str(value));basis.set(basis_text)
                if not note.get().strip():note.set('T2 사용자 지정 요율 자동 계산')
                dialog.destroy()
                messagebox.showinfo('자동 산정','금액과 산정 근거를 입력란에 반영했습니다.\n'
                    '기존 [추가 / 선택 행 수정] 버튼을 눌러 확정하세요.',parent=win)
            buttons=ttk.Frame(dialog,padding=8);buttons.pack()
            ttk.Button(buttons,text='계산 미리보기',command=preview).pack(side='left',padx=6)
            ttk.Button(buttons,text='기존 항목 입력란에 반영',command=transfer).pack(side='left',padx=6)
            ttk.Button(buttons,text='취소',command=dialog.destroy).pack(side='left',padx=6)
        ttk.Button(actions, text='요율 자동 산정 (T2)', command=auto_calculate).pack(side='left', padx=4)
        ttk.Button(actions, text='추가 / 선택 행 수정', command=apply).pack(side='left', padx=4)
        ttk.Button(actions, text='선택 삭제', command=delete).pack(side='left', padx=4)
        ttk.Button(actions, text='신규 항목 입력', command=clear_selection).pack(side='left', padx=4)
        total_var = tk.StringVar()
        ttk.Label(win, textvariable=total_var, padding=8, wraplength=980).pack(anchor='w')
        def replace(items):
            for row in tree.get_children(): tree.delete(row)
            for item in items:
                tree.insert('', 'end', values=(item.category,item.name,str(item.amount),item.basis,item.note))
            clear_selection(); refresh()
        def save():
            try:
                items = read_all()
                path = filedialog.asksaveasfilename(parent=win, title='입력 내역 저장',
                    defaultextension='.json', filetypes=[('JSON','*.json')])
                if path:
                    save_json(path, items)
                    messagebox.showinfo('저장 완료', path, parent=win)
            except (ValueError,OSError) as exc:
                messagebox.showerror('저장 실패',str(exc),parent=win)
        def load():
            path = filedialog.askopenfilename(parent=win, title='입력 내역 불러오기',
                                              filetypes=[('JSON','*.json')])
            if not path:return
            try: replace(load_json(path))
            except (ValueError,KeyError,TypeError,OSError) as exc:
                messagebox.showerror('불러오기 실패',str(exc),parent=win)
        def export():
            try:
                items = read_all()
                if not items:raise ValueError('출력할 비용 항목이 없습니다.')
                path = filedialog.asksaveasfilename(parent=win, title='공사비 외 비용 산정서',
                    defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')])
                if path:
                    export_xlsx(path, items)
                    self.log(f'공사비 외 비용 산정서 저장: {path}')
                    messagebox.showinfo('출력 완료','공사비 외 비용 XLSX 저장 완료\\n(총사업비 아님)',parent=win)
            except (ValueError,OSError,ImportError) as exc:
                messagebox.showerror('출력 실패',str(exc),parent=win)
        ttk.Button(actions, text='JSON 불러오기', command=load).pack(side='right', padx=4)
        ttk.Button(actions, text='JSON 저장', command=save).pack(side='right', padx=4)
        ttk.Button(actions, text='XLSX 출력', command=export).pack(side='right', padx=4)
        replace([CostItem(category, title, parse_amount('0')) for category,title in DEFAULT_ITEMS])

    def open_system_building_cost_dialog(self):
        """S1 isolated manual quantity/price ledger; P1 remains unchanged."""
        from system_building_cost import GROUPS,Item,number,amount,validate,summary,save_json,load_json,export_xlsx
        win=tk.Toplevel(self);win.title('v12.8-S2.3-HF2 궤도·시스템·건축 공사비');win.geometry('1120x660');win.transient(self.winfo_toplevel())
        ttk.Label(win,text='신규 공종별 수량 × 사용자 입력 단가(원). 항목이 없는 공종은 미산정입니다. D5/P1과 별도 관리.',padding=9).pack(anchor='w')
        cols=('공종','항목명','수량','단위','단가(원)','금액(원)','산정 근거','비고')
        tree=ttk.Treeview(win,columns=cols,show='headings',height=12)
        for c,w in zip(cols,(90,150,95,65,120,130,230,160)):
            tree.heading(c,text=c);tree.column(c,width=w,anchor='e' if c in ('수량','단가(원)','금액(원)') else 'w')
        tree.pack(fill='both',expand=True,padx=8,pady=5)
        frame=ttk.LabelFrame(win,text='항목 추가 / 선택 행 수정',padding=8);frame.pack(fill='x',padx=8)
        vars=[tk.StringVar(value=v) for v in (GROUPS[0],'','1','식','0','','')]
        labels=('공종','항목명','수량','단위','단가(원)','산정 근거','비고')
        for j,(label,var) in enumerate(zip(labels,vars)):
            ttk.Label(frame,text=label).grid(row=0,column=j,sticky='w')
            if j==0:widget=ttk.Combobox(frame,textvariable=var,values=GROUPS,state='readonly',width=12)
            else:widget=ttk.Entry(frame,textvariable=var,width=30 if j==5 else 15)
            widget.grid(row=1,column=j,padx=3,sticky='ew');frame.columnconfigure(j,weight=2 if j==5 else 1)
        selected=[None]
        def pick(_=None):
            ids=tree.selection()
            if not ids:return
            selected[0]=ids[0];v=tree.item(ids[0],'values')
            for var,value in zip(vars,(v[0],v[1],v[2],v[3],v[4],v[6],v[7])):var.set(value)
        tree.bind('<<TreeviewSelect>>',pick)
        def read_all():
            return validate([Item(v[0],v[1],number(v[2],'수량'),v[3],number(v[4],'단가'),v[6],v[7]) for v in (tree.item(k,'values') for k in tree.get_children())])
        status=tk.StringVar()
        def refresh():
            try:
                totals=summary(read_all());parts=[f'{g}: '+(f'{int(v):,}원' if v is not None else '미산정') for g,v in totals.items()]
                status.set('  |  '.join(parts)+f'  |  산정분 합계: {int(sum((v for v in totals.values() if v is not None),0)):,}원')
            except ValueError as exc:status.set(str(exc))
        def clear():
            selected[0]=None;tree.selection_remove(tree.selection())
            for var,value in zip(vars,(GROUPS[0],'','1','식','0','','')):var.set(value)
        def apply():
            try:
                i=Item(vars[0].get(),vars[1].get(),number(vars[2].get(),'수량'),vars[3].get(),number(vars[4].get(),'단가'),vars[5].get(),vars[6].get())
                others=[Item(v[0],v[1],number(v[2],'수량'),v[3],number(v[4],'단가'),v[6],v[7]) for k in tree.get_children() if k!=selected[0] for v in [tree.item(k,'values')]]
                validate(others+[i]);values=(i.group,i.name,str(i.quantity),i.unit,str(i.unit_price),str(amount(i)),i.basis,i.note)
                if selected[0] and tree.exists(selected[0]):tree.item(selected[0],values=values)
                else:tree.insert('', 'end',values=values)
                clear();refresh()
            except (ValueError,TypeError) as exc:messagebox.showerror('입력 오류',str(exc),parent=win)
        def delete():
            for k in tree.selection():tree.delete(k)
            clear();refresh()
        def replace(items):
            for k in tree.get_children():tree.delete(k)
            for i in items:tree.insert('', 'end',values=(i.group,i.name,str(i.quantity),i.unit,str(i.unit_price),str(amount(i)),i.basis,i.note))
            clear();refresh()
        selected_kdi = {"row": None, "db": None}
        def choose_kdi_price():
            from kdi_shared_picker import open_kdi_picker
            from system_kdi_link import provenance
            from system_building_cost import GROUPS
            def apply_kdi(row, db_name):
                vars[0].set(row['group'])
                vars[1].set(row['name'] + ((' - '+str(row.get('spec'))) if row.get('spec') else ''))
                vars[3].set(row['unit'])
                vars[4].set(str(row['source_price_krw']))
                vars[5].set(provenance(row, db_name))
                selected_kdi['row'] = row
                selected_kdi['db'] = db_name
            open_kdi_picker(win, apply_kdi, groups=GROUPS, initial_group=vars[0].get())
        def link_track_length():
            from track_length_link import segment_lengths,quantity_for_price
            from system_kdi_link import load_eligible_catalog
            from pathlib import Path
            try:
                source,alignment=self.get_context()
                if not source or alignment is None:
                    raise ValueError('먼저 종단 DXF를 불러오고 선형 계산을 완료하세요.')
                lengths=segment_lengths(alignment.vips,self.segments)
            except (ValueError,TypeError,AttributeError) as exc:
                messagebox.showerror('궤도연장 연동',str(exc),parent=win);return
            popup=tk.Toplevel(win);popup.title('S2.1.1 궤도연장 자동 연동');popup.geometry('700x390');popup.transient(win)
            popup.grab_set()
            ttk.Label(popup,text='현재 선형/구조물 목록에서 연장을 계산합니다. 궤도 수와 구간은 직접 확인하세요.',padding=8).pack(anchor='w')
            for g,v in lengths.items():
                ttk.Label(popup,text=f'{g}: {v:,.3f}m',padding=2).pack(anchor='w',padx=12)
            count=tk.StringVar(value='1');scope=tk.StringVar(value='전체')
            line=ttk.Frame(popup,padding=8);line.pack(fill='x')
            ttk.Label(line,text='선로 수').pack(side='left')
            ttk.Combobox(line,textvariable=count,values=('1','2'),state='readonly',width=8).pack(side='left',padx=8)
            ttk.Label(line,text='적용 구간').pack(side='left',padx=10)
            ttk.Combobox(line,textvariable=scope,values=tuple(lengths),state='readonly',width=12).pack(side='left',padx=8)
            ttk.Label(popup,text='먼저 S2.1 KDI 궤도 단가를 선택하세요. 현재 입력란의 단가코드를 근거에서 확인합니다.',padding=7,wraplength=650).pack(anchor='w')
            def apply_length():
                try:
                    import re
                    basis = vars[5].get()
                    m = re.search(r'KDI 단가 DB 선택:\s*([A-Za-z0-9_]+)', basis)
                    if not m:
                        raise ValueError('먼저 [KDI 단가 선택]에서 궤도 단가를 선택하세요.')
                    code = m.group(1)
                    row = selected_kdi['row']
                    if row is None or row['code'] != code:
                        db = Path(__file__).with_name('kdi_general_rail_2019.json')
                        entries = load_eligible_catalog(db)
                        row = next((x for x in entries if x['code'] == code), None)
                    if row is None:
                        raise ValueError('선택한 단가 코드가 동봉 DB에 없습니다. 단가 DB를 확인하세요.')
                    if vars[0].get()!=row['group'] or vars[3].get()!=row['unit'] or str(vars[4].get()).replace(',','')!=str(row['source_price_krw']):
                        raise ValueError('입력란의 공종·단위·단가가 KDI 선택 항목과 다릅니다.')
                    q=quantity_for_price(row,lengths,int(count.get()),scope.get())
                    if q<=0:raise ValueError('선택 구간의 궤도연장이 0입니다.')
                    vars[2].set(str(q))
                    vars[5].set(vars[5].get()+f' | [S2.1.1 수량] {scope.get()} {lengths[scope.get()]}m × 선로수 {count.get()} / 단가단위 {row["unit"]} = {q}')
                    popup.destroy()
                    messagebox.showinfo('궤도연장 연동','수량을 입력란에 반영했습니다. [추가 / 선택 행 수정]을 눌러 확정하세요.',parent=win)
                except (ValueError,TypeError,StopIteration) as exc:
                    messagebox.showerror('궤도연장 연동',str(exc),parent=popup)
            ttk.Button(popup,text='선택한 KDI 단가에 연장 수량 적용',command=apply_length).pack(pady=12)
        def link_system_quantity():
            from system_quantity_link import selected_price,system_quantity
            from track_length_link import segment_lengths
            from system_kdi_link import load_eligible_catalog
            from pathlib import Path
            try:
                row=selected_price(vars[5].get(),selected_kdi['row'],
                    load_eligible_catalog(Path(__file__).with_name('kdi_general_rail_2019.json')))
                if row['group'] not in ('전력','전차선','신호','통신','건축'):
                    raise ValueError('이 버튼은 전력·전차선·신호·통신·건축 전용입니다. 궤도는 기존 궤도연장 버튼을 사용하세요.')
                if vars[0].get()!=row['group'] or vars[3].get()!=row['unit'] or str(vars[4].get()).replace(',','')!=str(row['source_price_krw']):
                    raise ValueError('선택 단가의 공종·단위·금액이 현재 입력란과 다릅니다.')
                if row['unit']=='km':
                    source,alignment=self.get_context()
                    if not source or alignment is None:raise ValueError('먼저 종단 DXF와 선형 계산을 완료하세요.')
                    lengths=segment_lengths(alignment.vips,self.segments)
                else:lengths={}
            except (ValueError,TypeError,AttributeError) as exc:
                messagebox.showerror('시스템 수량 연동',str(exc),parent=win);return
            pop=tk.Toplevel(win);pop.title('S2.3 공종별 수량 연동');pop.geometry('680x380');pop.transient(win);pop.grab_set()
            ttk.Label(pop,text=f'{row["group"]} / {row["name"]} / 단가단위: {row["unit"]}',padding=10).pack(anchor='w')
            if lengths:
                for g,v in lengths.items():ttk.Label(pop,text=f'{g}: {v:,.3f}m',padding=2).pack(anchor='w',padx=12)
            ttk.Label(pop,text='km 단가는 선로 수가 이미 반영된 노선 km 기준입니다. 복선 ×2를 하지 않습니다.',
                      wraplength=630,padding=6).pack(anchor='w')
            count=tk.StringVar(value='1')
            scope=tk.StringVar(value=('터널' if row['group']=='전력' and row['code'].endswith('_TUN')
                else ('토공' if row['group']=='전력' else
                      {'EARTH':'토공','BRIDGE':'교량','TUNNEL':'터널'}.get(row['code'].split('_')[-1],'전체')
                      if row['group']=='전차선' else '전체')))
            station=tk.StringVar(value='');area=tk.StringVar(value='')
            line=ttk.Frame(pop,padding=6);line.pack(fill='x')
            ttk.Label(line,text='선로 수').pack(side='left')
            ttk.Combobox(line,textvariable=count,values=('1','2'),width=6,state='readonly').pack(side='left',padx=6)
            ttk.Label(line,text='구간').pack(side='left')
            ttk.Combobox(line,textvariable=scope,values=tuple(lengths) if lengths else ('전체',),width=10,state='readonly').pack(side='left',padx=6)
            if row['unit']=='개소(역)':
                ttk.Label(line,text='역 개소수').pack(side='left')
                ttk.Entry(line,textvariable=station,width=10).pack(side='left',padx=6)
            if row['unit']=='m²':
                ttk.Label(line,text='건축면적(m²)').pack(side='left')
                ttk.Entry(line,textvariable=area,width=14).pack(side='left',padx=6)
            def apply_system():
                try:
                    n=int(count.get())
                    st=None
                    if row['unit']=='개소(역)':
                        from decimal import Decimal
                        st=Decimal(station.get())
                    ar=area.get() if row['unit']=='m²' else None
                    q,detail=system_quantity(row,lengths,n,stations=st,area=ar,scope=scope.get())
                    import re
                    original=re.sub(r'\s*\| \[S2\.3 수량\][^|]*','',vars[5].get())
                    vars[2].set(str(q))
                    vars[5].set(original+f' | [S2.3 수량] {detail} = {q} {row["unit"]}')
                    pop.destroy()
                    messagebox.showinfo('시스템 수량 연동','수량 입력란에 반영했습니다. [추가 / 선택 행 수정]을 눌러 확정하세요.',parent=win)
                except (ValueError,TypeError,ArithmeticError) as exc:
                    messagebox.showerror('수량 산정 오류',str(exc),parent=pop)
            ttk.Button(pop,text='선택 단가에 수량 적용',command=apply_system).pack(pady=12)
        def batch_section_link():
            from system_quantity_link import selected_price,matching_section_prices,batch_section_quantities
            from system_kdi_link import load_eligible_catalog,provenance
            from track_length_link import segment_lengths
            from pathlib import Path
            try:
                catalog=load_eligible_catalog(Path(__file__).with_name('kdi_general_rail_2019.json'))
                row=selected_price(vars[5].get(),selected_kdi['row'],catalog)
                if row['group'] not in ('전력','전차선'):
                    raise ValueError('구간별 일괄 산정은 전력(개략)·전차선(세부) 전용입니다.')
                if vars[0].get()!=row['group'] or vars[3].get()!=row['unit'] or str(vars[4].get()).replace(',','')!=str(row['source_price_krw']):
                    raise ValueError('선택한 KDI 단가와 현재 입력란의 공종·단위·단가가 다릅니다.')
                choices=matching_section_prices(row,catalog)
                source,alignment=self.get_context()
                if not source or alignment is None:raise ValueError('먼저 종단 DXF와 선형 계산을 완료하세요.')
                lengths=segment_lengths(alignment.vips,self.segments)
            except (ValueError,TypeError,AttributeError) as exc:
                messagebox.showerror('구간별 수량 연동',str(exc),parent=win);return
            pop=tk.Toplevel(win);pop.title('S2.3-HF1 개략·세부 구간별 산정');pop.geometry('780x460');pop.transient(win);pop.grab_set()
            ttk.Label(pop,text=f'{row["group"]} / {row.get("method")} / 선택 기준: {row["code"]}',padding=10).pack(anchor='w')
            ttk.Label(pop,text='구간마다 원문 단가가 다른 경우 별도 내역으로 생성합니다. 가격이 없는 구간은 자동 산정하지 않습니다.',wraplength=730,padding=6).pack(anchor='w')
            counts=tk.StringVar(value='1' if '_S_' in row['code'] or row['code'].startswith('POWER_S_') else '2')
            bar=ttk.Frame(pop,padding=7);bar.pack(anchor='w')
            ttk.Label(bar,text='선로 수').pack(side='left')
            ttk.Combobox(bar,textvariable=counts,values=('1','2'),width=7,state='readonly').pack(side='left',padx=8)
            checked={}
            for scope,price in choices.items():
                line=ttk.Frame(pop,padding=6);line.pack(fill='x')
                enabled=price is not None and lengths.get(scope,0)>0
                checked[scope]=tk.BooleanVar(value=False)
                ttk.Checkbutton(line,text=scope,variable=checked[scope],state='normal' if enabled else 'disabled').pack(side='left')
                description=(f'{lengths.get(scope,0):,.3f}m / {price["source_price_krw"]:,}원/km / {price["code"]}'
                             if price is not None else f'{lengths.get(scope,0):,.3f}m / 검증된 단가 없음 (미산정)')
                ttk.Label(line,text=description).pack(side='left',padx=12)
            def commit_batch():
                try:
                    scopes=[scope for scope,v in checked.items() if v.get()]
                    rows=batch_section_quantities(row,catalog,lengths,int(counts.get()),scopes)
                    from system_building_cost import Item,amount,validate
                    from decimal import Decimal
                    current=read_all()
                    added=[]
                    for scope,price,q,basis in rows:
                        name=f'{price["name"]} - {price.get("spec","")} [{scope} / {price["code"]}]'
                        provenance_text=provenance(price,'kdi_general_rail_2019.json').replace(' | 수량 근거 별도 확인 필요','')
                        added.append(Item(price['group'],name,q,price['unit'],Decimal(price['source_price_krw']),
                                          provenance_text+f' | [S2.3-HF1 {price.get("method")}] {basis} = {q} {price["unit"]}',
                                          f'구간별 산정 / {scope}'))
                    validate(current+added)  # all-or-nothing; includes duplicate item protection
                    for i in added:
                        tree.insert('','end',values=(i.group,i.name,str(i.quantity),i.unit,str(i.unit_price),str(amount(i)),i.basis,i.note))
                    clear();refresh();pop.destroy()
                    messagebox.showinfo('구간별 산정 완료',f'{len(added)}개 구간별 내역을 추가했습니다. JSON/XLSX 저장 전에 내역을 확인하세요.',parent=win)
                except (ValueError,TypeError,ArithmeticError) as exc:
                    messagebox.showerror('구간별 산정 오류',str(exc),parent=pop)
            ttk.Button(pop,text='선택 구간별 내역 일괄 추가',command=commit_batch).pack(pady=14)
        buttons=ttk.Frame(win,padding=7);buttons.pack(fill='x')
        ttk.Button(buttons,text='추가 / 선택 행 수정',command=apply).pack(side='left',padx=3)
        ttk.Button(buttons,text='선택 삭제',command=delete).pack(side='left',padx=3)
        ttk.Button(buttons,text='신규 항목',command=clear).pack(side='left',padx=3)
        ttk.Button(buttons,text='통합 KDI 단가 선택 (S2.2.1)',command=choose_kdi_price).pack(side='left',padx=3)
        ttk.Button(buttons,text='궤도연장 자동 연동 (S2.1.1)',command=link_track_length).pack(side='left',padx=3)
        ttk.Button(buttons,text='시스템·건축 수량 연동 (S2.3)',command=link_system_quantity).pack(side='left',padx=3)
        batch_bar=ttk.Frame(win,padding=(7,0));batch_bar.pack(fill='x')
        ttk.Button(batch_bar,text='전력·전차선 구간별 일괄 산정 (HF1)',command=batch_section_link).pack(side='left',padx=3)
        ttk.Label(win,textvariable=status,padding=8,wraplength=1080).pack(anchor='w')
        def save():
            try:
                items=read_all()
                if not items:raise ValueError('저장할 항목이 없습니다.')
                path=filedialog.asksaveasfilename(parent=win,defaultextension='.json',filetypes=[('JSON','*.json')])
                if path:save_json(path,items);messagebox.showinfo('완료','JSON 저장 완료',parent=win)
            except (ValueError,OSError) as exc:messagebox.showerror('저장 오류',str(exc),parent=win)
        def load():
            path=filedialog.askopenfilename(parent=win,filetypes=[('JSON','*.json')])
            if not path:return
            try:replace(load_json(path))
            except (ValueError,KeyError,TypeError,OSError) as exc:messagebox.showerror('불러오기 오류',str(exc),parent=win)
        def export():
            try:
                items=read_all()
                if not items:raise ValueError('출력할 항목이 없습니다.')
                path=filedialog.asksaveasfilename(parent=win,defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
                if path:export_xlsx(path,items);self.log(f'시스템·건축 공사비 XLSX: {path}');messagebox.showinfo('완료','S1 공사비 XLSX 출력 완료',parent=win)
            except (ValueError,OSError,ImportError) as exc:messagebox.showerror('출력 오류',str(exc),parent=win)
        ttk.Button(buttons,text='JSON 불러오기',command=load).pack(side='right',padx=3)
        ttk.Button(buttons,text='JSON 저장',command=save).pack(side='right',padx=3)
        ttk.Button(buttons,text='XLSX 출력',command=export).pack(side='right',padx=3)
        refresh()

    def open_project_cost_dialog(self):
        """P1: combine two independently exported snapshots, never change D5/T2."""
        from project_cost import aggregate, export_project_cost
        from pathlib import Path
        win=tk.Toplevel(self)
        win.title('v12.7.5-P1 총사업비 산정분 통합')
        win.geometry('850x440')
        win.transient(self.winfo_toplevel())
        ttk.Label(win,text='D5 통합 공사비 XLSX + T1/T2 공사비 외 비용 JSON (전체 총사업비는 미확정)',padding=10).pack(anchor='w')
        paths={};labels={}
        for key,title,types in (
            ('construction','D5 통합 공사비 XLSX',[('Excel','*.xlsx')]),
            ('other','T1/T2 공사비 외 비용 JSON',[('JSON','*.json')])):
            row=ttk.Frame(win,padding=6);row.pack(fill='x')
            ttk.Label(row,text=title,width=30).pack(side='left')
            var=tk.StringVar(value='미선택');labels[key]=var
            ttk.Label(row,textvariable=var,width=58).pack(side='left',fill='x',expand=True)
            def choose(k=key,t=types):
                filename=filedialog.askopenfilename(parent=win,filetypes=t)
                if filename:paths[k]=filename;labels[k].set(Path(filename).name)
            ttk.Button(row,text='찾아보기',command=choose).pack(side='right')
        display=tk.Text(win,height=12,wrap='word',state='disabled')
        display.pack(fill='both',expand=True,padx=12,pady=8)
        result=[None]
        def preview():
            try:
                r=aggregate(paths.get('construction',''),paths.get('other',''))
                result[0]=r
                lines=['[산정분 합계] {:,}원'.format(int(r.subtotal)),
                       '전체 총사업비: 미확정', '', '[노반 공사비]']
                lines.extend(f'{g}: {int(v):,}원' for g,v in r.construction)
                lines+=['','[공사비 외 비용]']
                lines.extend(f'{g}: {int(v):,}원' for g,v in r.other)
                lines+=['','[미산정 공종] '+', '.join(r.missing),
                        '', '※ D5의 세부 누락 항목 및 부가세·가격 기준연도·중복은 별도 검증 필요']
                display.config(state='normal');display.delete('1.0','end');display.insert('end','\n'.join(lines));display.config(state='disabled')
            except (ValueError,OSError,KeyError,TypeError) as exc:
                result[0]=None;messagebox.showerror('통합 검증 실패',str(exc),parent=win)
        def export():
            preview()
            if result[0] is None:return
            filename=filedialog.asksaveasfilename(parent=win,defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
            if not filename:return
            try:
                export_project_cost(filename,result[0]);self.log(f'총사업비 산정분 통합 XLSX: {filename}')
                messagebox.showinfo('출력 완료','총사업비 산정분 XLSX 출력 완료 (전체 총사업비 미확정)',parent=win)
            except (ValueError,OSError,ImportError) as exc:messagebox.showerror('출력 실패',str(exc),parent=win)
        row=ttk.Frame(win,padding=8);row.pack(fill='x')
        ttk.Button(row,text='원본 검증 및 미리보기',command=preview).pack(side='left',padx=6)
        ttk.Button(row,text='총사업비 산정분 XLSX 출력',command=export).pack(side='right',padx=6)

    def open_integrated_cost_dialog(self):
        """D5: exclusive rough/detail choice for each work group, from exported XLSX."""
        from cost_decision_engine import GROUPS, read_cost_workbook, decide_costs, export_integrated_cost
        win=tk.Toplevel(self);win.title('v12.7.3-D5 통합 공사비 산정');win.geometry('790x405')
        ttk.Label(win,text='기존 개략/세부 공사비 XLSX를 불러오고 공종별 산정 방식을 하나만 선택합니다.',padding=10).pack(anchor='w')
        paths={};labels={}
        for mode,title in (('ROUGH','개략 공사비 XLSX'),('DETAIL','세부 공사비 XLSX')):
            row=ttk.Frame(win,padding=5);row.pack(fill='x')
            ttk.Label(row,text=title,width=22).pack(side='left')
            var=tk.StringVar(value='미선택');labels[mode]=var
            ttk.Label(row,textvariable=var,width=58).pack(side='left',fill='x',expand=True)
            def browse(m=mode):
                p=filedialog.askopenfilename(parent=win,title='공사비 산정서 선택',filetypes=[('Excel','*.xlsx')])
                if p:
                    try:
                        lines=read_cost_workbook(p,m)
                        paths[m]=p;labels[m].set(f'{p.split("/")[-1]} ({len(lines)}행)')
                    except (ValueError,OSError,ImportError) as exc:messagebox.showerror('원본 검증',str(exc),parent=win)
            ttk.Button(row,text='불러오기...',command=browse).pack(side='right')
        ttk.Label(win,text='공종별 채택 방식 (개략·세부를 동시에 합산하지 않음)',padding=8).pack(anchor='w')
        selections={}
        for group in GROUPS:
            row=ttk.Frame(win,padding=4);row.pack(fill='x',padx=10)
            ttk.Label(row,text=group,width=14).pack(side='left')
            var=tk.StringVar(value='미산정');selections[group]=var
            ttk.Combobox(row,textvariable=var,values=['미산정','개략','세부'],state='readonly',width=20).pack(side='left')
        ttk.Label(win,text='주의: 세부 산정에 빠진 공종 내 항목을 개략비로 자동 보충하지 않습니다. 원본의 기준연도·포함범위를 확인하세요.',
                  wraplength=750,padding=10).pack(anchor='w')
        def run():
            try:
                modes={'개략':'ROUGH','세부':'DETAIL','미산정':'NONE'}
                chosen,audit=decide_costs(paths.get('ROUGH'),paths.get('DETAIL'),
                                          {g:modes[v.get()] for g,v in selections.items()})
                if not chosen:raise ValueError('산정 대상이 없습니다. 원본과 공종별 채택 방식을 선택하세요.')
                msg='\\n'.join(f'{g}: {m} / {sum(x.amount for x in chosen if x.group==g):,.0f}원' for g,m,*_ in audit)
                if not messagebox.askyesno('통합 공사비 검토',msg+'\\n\\n각 공종별 포함범위와 기준연도가 일치합니까?',parent=win):return
                out=filedialog.asksaveasfilename(parent=win,title='통합 공사비 XLSX 저장',defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
                if not out:return
                export_integrated_cost(out,chosen,audit,paths.get('ROUGH'),paths.get('DETAIL'))
                self.log(f'통합 공사비 산정서 저장: {out}')
                messagebox.showinfo('통합 공사비','저장 완료 (산정분 합계; 총사업비 아님)',parent=win)
            except (ValueError,TypeError,OSError,ImportError,KeyError) as exc:messagebox.showerror('통합 공사비',str(exc),parent=win)
        ttk.Button(win,text='중복 검증 후 통합 XLSX 산출...',command=run).pack(pady=10)

    def open_cost_estimate_dialog(self):
        from cost_rough_engine import available_rough, estimate_rough, export_cost_xlsx
        from quantity_price import load_config
        opts=available_rough()
        win=tk.Toplevel(self);win.title('v12.7.2 개략 공사비 산정');win.geometry('820x290')
        ttk.Label(win,text='공종별 KDI 개략 단가를 직접 선택하세요. 미선택 공종은 미산정으로 표시합니다.',padding=8).pack(anchor='w')
        ttk.Label(win,text='선택 조건(단복선/지역/기초)은 자동 판정하지 않습니다. 세부 단가와 중복 계산하지 않습니다.',padding=8).pack(anchor='w')
        vars={};lookup={}
        for group in ('토공','교량','터널'):
            row=ttk.Frame(win,padding=5);row.pack(fill='x')
            ttk.Label(row,text=group,width=8).pack(side='left')
            names=['미선택 (미산정)']
            for item in opts[group]:
                label=f"{item['code']} | {item['spec']} | {item['condition']}"
                names.append(label);lookup[label]=item['code']
            v=tk.StringVar(value=names[0]);vars[group]=v
            ttk.Combobox(row,textvariable=v,values=names,state='readonly',width=92).pack(side='left',fill='x',expand=True)
        def run():
            try:
                source,alignment=self.get_context()
                if not source or alignment is None:raise ValueError('먼저 종단 DXF를 불러오고 계산을 완료하세요.')
                width,cut,fill=(float(v.get()) for v in self.earthwork_vars)
                earth=calculate_earthwork(read_ground_points(source),alignment,self.segments,width,cut,fill)
                selections={g:lookup.get(v.get(),'') for g,v in vars.items()}
                config=load_config()
                rows,review,lengths=estimate_rough(earth,self.segments,selections,config=config)
                if not rows:raise ValueError('산정 가능한 단가를 최소 1개 선택하세요.')
                path=filedialog.asksaveasfilename(parent=win,title='개략 공사비 산정서 저장',defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
                if not path:return
                export_cost_xlsx(path,rows,review,lengths,config)
                self.log(f'개략 공사비 산정서 저장: {path}')
                messagebox.showinfo('개략 공사비',f'저장 완료\n미산정 공종 {len(review)}건 (검토 시트 확인)',parent=win)
                win.destroy()
            except (ValueError,TypeError,OSError,ImportError) as exc:
                messagebox.showerror('개략 공사비',str(exc),parent=win)
        ttk.Button(win,text='공사비 XLSX 산출...',command=run).pack(pady=12)

    def export_integrated_quantities(self):
        try:
            source,alignment=self.get_context()
            if not source or alignment is None:
                raise ValueError('먼저 종단 DXF를 불러오고 계산을 완료하세요.')
            width,cut,fill=(float(v.get()) for v in self.earthwork_vars)
            earth=calculate_earthwork(read_ground_points(source),alignment,self.segments,width,cut,fill)
            girder=self.girder_settings()
            structures=calculate_structure_quantities(self.segments,girder)
            bridge_section=self.plan_section_path.get().strip() or None
            bridges=calculate_bridge_quantities(self.segments,girder,self.plan_pier_settings(),
                self.pier_settings(),bridge_section) if any(x.kind=='BRIDGE' for x in self.segments) else []
            tunnel_section=self.tunnel_section_path.get().strip() if self.tunnel_section_mode.get()=='dxf' else None
            tunnels=calculate_tunnel_quantities(self.segments,tunnel_section) if tunnel_section and any(x.kind=='TUNNEL' for x in self.segments) else []
            path=filedialog.asksaveasfilename(parent=self,title='통합 수량산출서 저장',
                defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
            if not path:return
            export_integrated_xlsx(path,earth,structures,bridges,tunnels,bridge_section,tunnel_section)
            self.log(f'통합 수량산출서 저장: {path}')
            messagebox.showinfo('통합 수량산출서','XLSX 저장 완료',parent=self)
        except (ValueError,TypeError,OSError,ImportError) as exc:
            messagebox.showerror('통합 수량산출서',str(exc),parent=self)

    def export_bridge_quantities(self):
        try:
            if not any(s.kind=='BRIDGE' for s in self.segments):
                raise ValueError('현재 구조물 목록에 교량이 없습니다.')
            section_path=self.plan_section_path.get().strip() or None
            rows=calculate_bridge_quantities(self.segments,self.girder_settings(),
                self.plan_pier_settings(),self.pier_settings(),section_path)
            path=filedialog.asksaveasfilename(parent=self,title='교량 수량산출서 저장',
                defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
            if not path:return
            export_bridge_xlsx(rows,path,section_path)
            self.log(f'교량 수량산출: {len(rows)}개, 총연장 {sum(r.length_m for r in rows):,.3f}m → {path}')
            messagebox.showinfo('교량 수량산출','XLSX 수량산출서 저장 완료',parent=self)
        except (ValueError,TypeError,OSError,ImportError) as exc:
            messagebox.showerror('교량 수량산출',str(exc),parent=self)

    def export_tunnel_quantities(self):
        try:
            if not any(s.kind=='TUNNEL' for s in self.segments):
                raise ValueError('현재 구조물 목록에 터널이 없습니다.')
            if self.tunnel_section_mode.get()!='dxf':
                raise ValueError('터널 설정에서 사용자 단면 DXF를 선택하세요. 기본 사각 단면은 폭이 정의되지 않아 수량산출에서 제외합니다.')
            section_path=self.tunnel_section_path.get().strip()
            rows=calculate_tunnel_quantities(self.segments,section_path)
            path=filedialog.asksaveasfilename(parent=self,title='터널 수량산출서 저장',
                defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
            if not path:return
            export_tunnel_xlsx(rows,path,section_path)
            self.log(f'터널 수량산출: {len(rows)}개, 굴착 {sum(r.excavation_m3 for r in rows):,.3f}m³, 라이닝 {sum(r.lining_m3 for r in rows):,.3f}m³ → {path}')
            messagebox.showinfo('터널 수량산출','XLSX 수량산출서 저장 완료',parent=self)
        except (ValueError,TypeError,OSError,ImportError) as exc:
            messagebox.showerror('터널 수량산출',str(exc),parent=self)

    def export_basic_quantities(self):
        try:
            if not self.segments:
                raise ValueError('수량을 산출할 구조물 목록이 없습니다.')
            rows=calculate_structure_quantities(self.segments,self.girder_settings())
            path=filedialog.asksaveasfilename(parent=self,title='구조물 기본 수량산출서 저장',
                defaultextension='.xlsx',filetypes=[('Excel 수량산출서','*.xlsx')])
            if not path: return
            export_quantities_xlsx(rows,path)
            self.log(f'구조물 기본 수량산출서 저장: {path} (교량 {sum(r.kind=="BRIDGE" for r in rows)}개, 터널 {sum(r.kind=="TUNNEL" for r in rows)}개)')
        except (ValueError,TypeError,OSError,ImportError) as exc:
            messagebox.showerror('구조물 기본 수량산출',str(exc),parent=self)

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
