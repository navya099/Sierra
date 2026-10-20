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
        ttk.Button(actions,text='기본 수량산출 XLSX...',command=self.export_basic_quantities).pack(side='left',padx=3)
        ttk.Button(actions,text='개략 토공량...',command=self.open_earthwork_dialog).pack(side='left',padx=3)
        ttk.Button(actions,text='터널 수량 XLSX...',command=self.export_tunnel_quantities).pack(side='left',padx=3)
        ttk.Button(actions,text='교량 수량 XLSX...',command=self.export_bridge_quantities).pack(side='left',padx=3)
        ttk.Button(actions,text='통합 수량산출서 XLSX...',command=self.export_integrated_quantities).pack(side='left',padx=3)
        ttk.Button(actions,text='KDI 단가 관리...',command=self.open_unit_price_manager).pack(side='left',padx=3)
        ttk.Button(actions,text='개략 공사비 XLSX...',command=self.open_cost_estimate_dialog).pack(side='left',padx=3)
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

    def open_cost_estimate_dialog(self):
        from cost_estimate import available_rough, estimate_rough, export_cost_xlsx
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
