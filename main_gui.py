"""Railway vertical alignment GUI (Tkinter / optional tkinterdnd2).

Place beside dxf_reader.py, profile_calculator.py and dxf_watcher.py.
The design DXF is created once and subsequently treated as read-only by Python.
"""
from __future__ import annotations

import math
import os
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import ezdxf

from dxf_watcher import DXFWatcher
from profile_scale import ProfileScale
from profile_drawing import DrawingOptions, create_profile_drawing
from final_plan_vip import create_final_plan
from vertical_curve import VerticalAlignment
from structure_gui import StructureEditor

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    RootClass = TkinterDnD.Tk
    HAS_DND = True
except ImportError:
    RootClass = tk.Tk
    HAS_DND = False


def parse_ground_txt(path: Path) -> list[tuple[float, float]]:
    points = []
    with path.open('r', encoding='utf-8-sig') as stream:
        for lineno, raw in enumerate(stream, 1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            fields = line.replace(',', ' ').split()
            if len(fields) != 2:
                raise ValueError(f'TXT {lineno}행: 측점과 표고 2개 값이 필요합니다.')
            try:
                x, y = map(float, fields)
            except ValueError as exc:
                raise ValueError(f'TXT {lineno}행: 숫자를 해석할 수 없습니다.') from exc
            if not (math.isfinite(x) and math.isfinite(y)):
                raise ValueError(f'TXT {lineno}행: 유한한 숫자만 사용할 수 있습니다.')
            if points and x <= points[-1][0]:
                raise ValueError(f'TXT {lineno}행: 측점은 엄격히 증가해야 합니다.')
            points.append((x, y))
    if len(points) < 2:
        raise ValueError('지반고 좌표가 최소 2개 필요합니다.')
    return points


def create_design_dxf(txt_path: Path, output_path: Path, scale: ProfileScale | None = None) -> None:
    points = parse_ground_txt(txt_path)
    if output_path.exists():
        raise FileExistsError(f'기존 설계 파일을 보호하기 위해 덮어쓰지 않습니다: {output_path}')
    doc = ezdxf.new('R2010')
    doc.layers.new('GROUND_PROFILE', dxfattribs={'color': 8})
    doc.layers.new('PLAN_PROFILE', dxfattribs={'color': 1})
    doc.modelspace().add_lwpolyline(points, format='xy', dxfattribs={'layer': 'GROUND_PROFILE'})
    # PLAN_PROFILE must be drawn by the CAD operator; never invent an alignment.
    doc.saveas(str(output_path))


class AlignmentGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title('종단선형 설계 프로그램')
        root.geometry('1120x770')
        root.minsize(850, 610)
        self.file_var = tk.StringVar(value='불러온 파일 없음')
        self.interval_var = tk.StringVar(value='25')
        self.status_var = tk.StringVar(value='대기 중')
        self.range_var = tk.StringVar(value='—')
        self.vip_count_var = tk.StringVar(value='—')
        self.max_grade_var = tk.StringVar(value='—')
        self.auto_var = tk.BooleanVar(value=True)
        self.dxf_path: Path | None = None
        self.last_vips = []
        self.last_stations = []
        self.vc_lengths = {}  # station (m) -> full vertical-curve length (m)
        self.vc_alignment = None
        self.events: queue.Queue = queue.Queue()
        self.stop_event: threading.Event | None = None
        self.worker: threading.Thread | None = None
        self.watcher: DXFWatcher | None = None
        self.generation = 0
        self.exporting = False
        self.closed = False
        self._build()
        self.root.after(100, self._drain_events)
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def _build(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label='지반고 TXT 불러오기', command=self.open_txt)
        file_menu.add_command(label='설계 DXF 불러오기', command=self.open_dxf)
        file_menu.add_separator()
        file_menu.add_command(label='도면 출력 DXF', command=self.export_drawing)
        file_menu.add_command(label='결과 CSV 폴더 열기', command=self.open_folder)
        file_menu.add_separator()
        file_menu.add_command(label='종료', command=self.close)
        menu.add_cascade(label='파일', menu=file_menu)
        tools = tk.Menu(menu, tearoff=False)
        tools.add_command(label='수동 재계산', command=self.recalculate)
        tools.add_command(label='자동 감시 시작', command=self.start_watch)
        tools.add_command(label='자동 감시 중지', command=self.stop_watch)
        menu.add_cascade(label='도구', menu=tools)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label='사용자 매뉴얼', command=self.show_manual)
        help_menu.add_command(label='프로그램 정보', command=lambda: messagebox.showinfo('프로그램 정보', '종단선형 설계 GUI v1.0\nDXF 기반 독립형 종단 분석'))
        menu.add_cascade(label='도움말', menu=help_menu)
        self.root.config(menu=menu)

        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill='both', expand=True)
        header = ttk.Frame(outer)
        header.pack(fill='x', pady=(0, 8))
        ttk.Label(header, text='종단선형 설계 및 분석', font=('맑은 고딕', 17, 'bold')).pack(side='left')
        ttk.Label(header, textvariable=self.status_var, foreground='#187c57').pack(side='right')

        source = ttk.LabelFrame(outer, text='1. 프로젝트 입력', padding=10)
        source.pack(fill='x', pady=4)
        drop = tk.Label(source, text='TXT 또는 DXF 파일을 여기에 드래그하세요' if HAS_DND else '파일 선택 버튼으로 TXT 또는 DXF를 불러오세요',
                        relief='groove', bd=1, height=2, bg='#f5f7fa', font=('맑은 고딕', 10))
        drop.pack(fill='x', pady=(0, 6))
        if HAS_DND:
            drop.drop_target_register(DND_FILES)
            drop.dnd_bind('<<Drop>>', self._on_drop)
        controls = ttk.Frame(source)
        controls.pack(fill='x')
        ttk.Button(controls, text='TXT 선택', command=self.open_txt).pack(side='left', padx=(0, 5))
        ttk.Button(controls, text='DXF 선택', command=self.open_dxf).pack(side='left', padx=(0, 10))
        ttk.Label(controls, textvariable=self.file_var).pack(side='left', fill='x', expand=True)

        summary = ttk.Frame(outer)
        summary.pack(fill='x', pady=5)
        settings = ttk.LabelFrame(summary, text='2. 계산 설정', padding=10)
        settings.pack(side='left', fill='both', expand=True, padx=(0, 6))
        ttk.Label(settings, text='증분측점 간격 (m)').grid(row=0, column=0, sticky='w')
        ttk.Entry(settings, textvariable=self.interval_var, width=9).grid(row=0, column=1, padx=8)
        ttk.Checkbutton(settings, text='CAD 저장 시 자동 분석', variable=self.auto_var, command=self._toggle_watch).grid(row=1, column=0, columnspan=2, sticky='w', pady=(7, 0))
        ttk.Button(settings, text='설정 적용 / 재계산', command=self.recalculate).grid(row=0, column=2, padx=8)
        ttk.Label(settings, text='측점 범위').grid(row=2, column=0, sticky='w', pady=(6, 0))
        ttk.Label(settings, textvariable=self.range_var).grid(row=2, column=1, columnspan=2, sticky='w', pady=(6, 0))
        info = ttk.LabelFrame(summary, text='3. 계산 요약', padding=10)
        info.pack(side='left', fill='both', expand=True)
        for i, (name, variable) in enumerate([('VIP 개수', self.vip_count_var), ('최대 절대구배', self.max_grade_var), ('분석 상태', self.status_var)]):
            ttk.Label(info, text=name).grid(row=i, column=0, sticky='w', padx=(0, 15), pady=2)
            ttk.Label(info, textvariable=variable).grid(row=i, column=1, sticky='w', pady=2)

        results = ttk.LabelFrame(outer, text='4. 실행 결과', padding=8)
        results.pack(fill='both', expand=True, pady=5)
        tabs = ttk.Notebook(results)
        tabs.pack(fill='both', expand=True)
        vip_frame = ttk.Frame(tabs)
        station_frame = ttk.Frame(tabs)
        log_frame = ttk.Frame(tabs)
        vc_frame = ttk.Frame(tabs)
        tabs.add(vip_frame, text='VIP 분석')
        tabs.add(station_frame, text='증분측점 계산')
        tabs.add(log_frame, text='실행 로그')
        tabs.add(vc_frame, text='종곡선 설계 (시험)')
        structure_frame = ttk.Frame(tabs)
        tabs.add(structure_frame, text='구조물 관리')
        self.structure_editor = StructureEditor(structure_frame, self._structure_context, self._log)
        self.structure_editor.pack(fill='both', expand=True)
        self.vip_tree = self._make_tree(vip_frame, ['구분', 'STA', 'EL', '진입(‰)', '진출(‰)', '변화(‰)'])
        self.station_tree = self._make_tree(station_frame, ['STA', '지반고', '계획고', '표고차', '구배(‰)', '구분'])
        vc_controls = ttk.Frame(vc_frame)
        vc_controls.pack(fill='x', pady=5)
        ttk.Label(vc_controls, text='선택 VIP 종곡선 길이 L (m)').pack(side='left', padx=5)
        self.vc_length_var = tk.StringVar(value='0')
        ttk.Entry(vc_controls, textvariable=self.vc_length_var, width=12).pack(side='left', padx=5)
        ttk.Button(vc_controls, text='길이 적용', command=self.apply_vc_length).pack(side='left', padx=5)
        ttk.Button(vc_controls, text='종곡선 계산', command=self.rebuild_vertical_curves).pack(side='left', padx=5)
        ttk.Button(vc_controls, text='계산 결과 CSV 저장', command=self.export_vc_csv).pack(side='left', padx=5)
        self.vc_draw_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(vc_frame, text='종평면도 DXF에 종곡선 적용 (시험 · 기본 OFF)',
                        variable=self.vc_draw_var).pack(anchor='w', padx=5)
        ttk.Label(vc_frame, text='내부 VIP 선택 후 L 입력 (0은 종곡선 없음). 체크 시 종평면도 계획선과 계획고 밴드에 반영됩니다.').pack(fill='x', padx=5)
        self.vc_tree = self._make_tree(vc_frame, ['VIP', 'STA', '접선교점 EL', 'L(m)', 'PVC', 'PVT', '종곡선 중심 EL', '중심 차이(m)'])
        self.vc_tree.bind('<<TreeviewSelect>>', self._on_vc_select)
        self.log_text = tk.Text(log_frame, wrap='word', height=12, state='disabled', font=('Consolas', 10))
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side='left', fill='both', expand=True)
        log_scroll.pack(side='right', fill='y')

        footer = ttk.Frame(outer)
        footer.pack(fill='x', pady=(6, 0))
        self.export_button = ttk.Button(footer, text='도면 출력 (DXF)', command=self.export_drawing, state='disabled')
        self.export_button.pack(side='left', padx=(0, 8))
        ttk.Button(footer, text='결과 CSV 열기', command=self.open_folder).pack(side='left')
        ttk.Button(footer, text='종료', command=self.close).pack(side='right')
        ttk.Button(footer, text='매뉴얼', command=self.show_manual).pack(side='right', padx=8)
        self._log('GUI 준비 완료. TXT 또는 DXF를 불러오세요.')
        if not HAS_DND:
            self._log('tkinterdnd2가 없어 드래그 앤 드롭은 비활성화되었습니다. 파일 선택은 가능합니다.')

    @staticmethod
    def _make_tree(parent, columns):
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill='both', expand=True)
        tree = ttk.Treeview(wrapper, columns=columns, show='headings', selectmode='browse')
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, anchor='center', width=125, minwidth=85, stretch=True)
        ybar = ttk.Scrollbar(wrapper, orient='vertical', command=tree.yview)
        xbar = ttk.Scrollbar(wrapper, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.grid(row=0, column=0, sticky='nsew')
        ybar.grid(row=0, column=1, sticky='ns')
        xbar.grid(row=1, column=0, sticky='ew')
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        return tree

    def _log(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f'[{datetime.now():%H:%M:%S}] {message}\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        if len(paths) != 1:
            messagebox.showwarning('입력 오류', '파일을 한 개씩 불러오세요.')
            return
        self.load_file(Path(paths[0]))

    def open_txt(self):
        path = filedialog.askopenfilename(filetypes=[('지반고 TXT', '*.txt'), ('모든 파일', '*.*')])
        if path:
            self.load_file(Path(path))

    def open_dxf(self):
        path = filedialog.askopenfilename(filetypes=[('DXF 도면', '*.dxf'), ('모든 파일', '*.*')])
        if path:
            self.load_file(Path(path))

    def load_file(self, path: Path):
        path = path.expanduser().resolve()
        if not path.is_file():
            messagebox.showerror('입력 오류', f'파일을 찾을 수 없습니다:\n{path}')
            return
        if path.suffix.lower() == '.txt':
            target = path.with_name('converted_dxf.dxf')
            if target.exists():
                if not messagebox.askyesno('기존 설계 보호',
                    f'이미 설계용 DXF가 있습니다.\n{target}\n\n기존 파일은 덮어쓰지 않습니다. 기존 DXF를 불러오시겠습니까?'):
                    return
            else:
                try:
                    create_design_dxf(path, target)
                except Exception as exc:
                    messagebox.showerror('DXF 생성 실패', str(exc))
                    return
                self._log(f'지반고 DXF 생성: {target}')
                messagebox.showinfo('DXF 생성 완료',
                    '지반고 DXF를 생성했습니다.\nCAD에서 PLAN_PROFILE 레이어에 계획 종단 LWPOLYLINE을 그린 뒤 저장하세요.\n그 전에는 계산 결과가 표시되지 않습니다.')
            path = target
        elif path.suffix.lower() != '.dxf':
            messagebox.showwarning('지원하지 않는 형식', 'TXT 또는 DXF만 불러올 수 있습니다.')
            return
        self.stop_watch()
        self.dxf_path = path
        self.vc_lengths.clear()
        self.structure_editor.clear_for_new_project()
        self.file_var.set(str(path))
        self._clear_results()
        self.status_var.set('DXF 감시 준비')
        self._log(f'설계용 DXF 연결: {path}')
        if self.auto_var.get():
            self.start_watch()
        else:
            self.recalculate()

    def _validated_interval(self):
        try:
            value = float(self.interval_var.get())
            if not math.isfinite(value) or value <= 0:
                raise ValueError
            return value
        except ValueError:
            messagebox.showwarning('계산 설정', '증분측점 간격에 양수인 숫자를 입력하세요.')
            return None

    def _toggle_watch(self):
        if self.auto_var.get():
            self.start_watch()
        else:
            self.stop_watch()
            self.status_var.set('자동 감시 중지')

    def start_watch(self):
        if self.dxf_path is None:
            return
        interval = self._validated_interval()
        if interval is None:
            return
        self.stop_watch()
        self.generation += 1
        generation = self.generation
        self.stop_event = threading.Event()
        self.watcher = DXFWatcher(
            self.dxf_path, interval=interval,
            on_update=lambda v, s: self.events.put((generation, 'update', (v, s))),
            on_error=lambda exc: self.events.put((generation, 'error', str(exc))),
        )
        watcher = self.watcher
        stop = self.stop_event
        self.worker = threading.Thread(target=watcher.run, args=(stop,), daemon=True)
        self.worker.start()
        self.status_var.set('자동 감시 중')
        self._log(f'자동 감시 시작 (증분 {interval:g}m): {self.dxf_path.name}')

    def stop_watch(self):
        self.generation += 1
        if self.stop_event is not None:
            self.stop_event.set()
        self.stop_event = None
        self.worker = None
        self.watcher = None

    def recalculate(self):
        if self.dxf_path is None:
            messagebox.showinfo('파일 필요', '먼저 TXT 또는 DXF 파일을 불러오세요.')
            return
        if self.auto_var.get():
            self.start_watch()  # New watcher reprocesses even if DXF bytes did not change.
        else:
            self.stop_watch()
            self._calculate_once()

    def _calculate_once(self):
        from dxf_reader import extract_profile, export_csv as export_vips
        from profile_calculator import calculate_stations, export_csv as export_stations
        path = self.dxf_path
        interval = self._validated_interval()
        if interval is None or path is None:
            return
        self.generation += 1
        generation = self.generation
        def work():
            try:
                vip = extract_profile(path)
                stations = calculate_stations(path, interval=interval)
                # The DXF remains untouched; CSV outputs are replaced atomically.
                from dxf_watcher import atomic_csv_write
                atomic_csv_write(vip, path.with_name('plan_profile_result.csv'), export_vips)
                atomic_csv_write(stations, path.with_name('profile_station_result.csv'), export_stations)
                self.events.put((generation, 'update', (vip, stations)))
            except Exception as exc:
                self.events.put((generation, 'error', str(exc)))
        threading.Thread(target=work, daemon=True).start()
        self.status_var.set('수동 계산 중')

    def _drain_events(self):
        if self.closed:
            return
        try:
            while True:
                generation, kind, data = self.events.get_nowait()
                if generation != self.generation and kind not in ('export_ok', 'export_error'):
                    continue
                if kind == 'update':
                    self._show_results(*data)
                elif kind == 'export_summary':
                    self._export_summary(data)
                elif kind == 'error':
                    self.status_var.set('분석 대기 / 오류')
                    self._log(f'분석 대기/오류: {data}')
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _clear_results(self):
        for tree in (self.vip_tree, self.station_tree):
            tree.delete(*tree.get_children())
        self.last_vips = []
        self.last_stations = []
        self.vc_alignment = None
        self.vc_tree.delete(*self.vc_tree.get_children())
        self.export_button.configure(state='disabled')
        self.range_var.set('—')
        self.vip_count_var.set('—')
        self.max_grade_var.set('—')

    def _show_results(self, vips, stations):
        self._clear_results()
        self.last_vips = vips
        self.last_stations = stations
        if not self.exporting:
            self.export_button.configure(state='normal')
        def fmt(v):
            return '—' if v is None else f'{v:+.3f}'
        for p in vips:
            self.vip_tree.insert('', 'end', values=(p.kind, f'{p.sta:.3f}', f'{p.elevation:.3f}', fmt(p.gradient_in), fmt(p.gradient_out), fmt(p.delta_gradient)))
        for r in stations:
            self.station_tree.insert('', 'end', values=(f'{r.sta:.3f}', f'{r.ground_el:.3f}', f'{r.plan_el:.3f}', fmt(r.difference), fmt(r.gradient_permille), r.classification))
        self.vip_count_var.set(f'{max(0, len(vips)-2)}개')
        grades = [abs(p.gradient_out) for p in vips if p.gradient_out is not None]
        self.max_grade_var.set(f'{max(grades):.3f}‰' if grades else '—')
        self.range_var.set(f'{stations[0].sta:.3f} ~ {stations[-1].sta:.3f} m' if stations else '—')
        self.status_var.set('분석 완료 / 감시 중' if self.auto_var.get() else '분석 완료')
        self._refresh_vc_table()
        self._log(f'분석 완료: VIP {max(0,len(vips)-2)}개, 측점 {len(stations)}개 / CSV 갱신')

    def _on_vc_select(self, _event=None):
        selected = self.vc_tree.selection()
        if selected:
            index = int(selected[0])
            if 0 < index < len(self.last_vips) - 1:
                self.vc_length_var.set(f'{self.vc_lengths.get(self.last_vips[index].sta, 0):g}')

    def apply_vc_length(self):
        selected = self.vc_tree.selection()
        if not selected:
            messagebox.showinfo('종곡선', '먼저 내부 VIP 행을 선택하세요.')
            return
        index = int(selected[0])
        if not 0 < index < len(self.last_vips) - 1:
            messagebox.showwarning('종곡선', 'BP/EP에는 종곡선을 지정할 수 없습니다.')
            return
        try:
            length = float(self.vc_length_var.get())
            if not math.isfinite(length) or length < 0:
                raise ValueError('L은 0 이상의 유한한 값이어야 합니다.')
            lengths = dict(self.vc_lengths)
            sta = self.last_vips[index].sta
            if length == 0:
                lengths.pop(sta, None)
            else:
                lengths[sta] = length
            self._make_vc_alignment(lengths)  # validate before committing
        except (ValueError, TypeError) as exc:
            messagebox.showerror('종곡선 길이 오류', str(exc))
            return
        self.vc_lengths = lengths
        self._refresh_vc_table(select_index=index)
        self._log(f'종곡선 길이 적용: VIP {index}, STA {sta:.3f}, L={length:g}m')

    def _structure_context(self):
        # Always rebuild from live VIP curve lengths, not a stale cached alignment.
        if not self.dxf_path or not self.last_vips:
            return self.dxf_path, None
        return self.dxf_path, self._make_vc_alignment(self.vc_lengths)

    def _make_vc_alignment(self, lengths):
        points = [(p.sta, p.elevation) for p in self.last_vips]
        if len(points) < 2:
            raise ValueError('종단 분석을 먼저 완료하세요.')
        indexes = {p.sta: i for i, p in enumerate(self.last_vips)}
        active = {indexes[sta]: L for sta, L in lengths.items() if sta in indexes and L > 0}
        return VerticalAlignment(points, active)

    def _refresh_vc_table(self, select_index=None):
        self.vc_tree.delete(*self.vc_tree.get_children())
        self.vc_alignment = None
        if len(self.last_vips) < 2:
            return
        try:
            alignment = self._make_vc_alignment(self.vc_lengths)
        except ValueError as exc:
            self._log(f'종곡선 재계산 오류: {exc}')
            return
        self.vc_alignment = alignment
        curves = {c.vip_index: c for c in alignment.curves}
        for i, p in enumerate(self.last_vips):
            curve = curves.get(i)
            center = curve.evaluate(p.sta)[0] if curve else p.elevation
            row = (p.kind, f'{p.sta:.3f}', f'{p.elevation:.3f}',
                   f'{curve.length:g}' if curve else '0',
                   f'{curve.pvc_sta:.3f}' if curve else '—',
                   f'{curve.pvt_sta:.3f}' if curve else '—',
                   f'{center:.3f}', f'{center - p.elevation:+.3f}')
            self.vc_tree.insert('', 'end', iid=str(i), values=row)
        if select_index is not None:
            self.vc_tree.selection_set(str(select_index))
            self.vc_tree.see(str(select_index))

    def rebuild_vertical_curves(self):
        self._refresh_vc_table()
        if self.vc_alignment is not None:
            self._log(f'종곡선 계산 완료: {len(self.vc_alignment.curves)}개')

    def export_vc_csv(self):
        if self.vc_alignment is None:
            messagebox.showwarning('종곡선', '종곡선 계산 결과가 없습니다.')
            return
        path = filedialog.asksaveasfilename(title='종곡선 계산 결과 CSV', defaultextension='.csv',
                                            initialfile='vertical_curve_result.csv',
                                            filetypes=[('CSV 파일', '*.csv')])
        if not path:
            return
        import csv
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(['VIP', 'VIP_STA', 'VIP_EL', 'L', 'PVC_STA', 'PVC_EL',
                                 'PVT_STA', 'PVT_EL', 'IN_GRADE_PERMILLE', 'OUT_GRADE_PERMILLE',
                                 'CURVE_CENTER_EL', 'CENTER_DIFF'])
                for c in self.vc_alignment.curves:
                    center = c.evaluate(c.vip_sta)[0]
                    writer.writerow([c.vip_index, c.vip_sta, c.vip_elevation, c.length,
                                     c.pvc_sta, c.pvc_elevation, c.pvt_sta, c.pvt_elevation,
                                     c.in_grade, c.out_grade, center, center-c.vip_elevation])
            self._log(f'종곡선 계산 CSV 저장: {path}')
        except OSError as exc:
            messagebox.showerror('CSV 저장 실패', str(exc))

    def open_folder(self):
        if self.dxf_path is None:
            messagebox.showinfo('파일 필요', '먼저 DXF를 불러오세요.')
            return
        folder = str(self.dxf_path.parent)
        try:
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception as exc:
            messagebox.showerror('폴더 열기 실패', str(exc))

    def _print_options(self):
        """Modal print-options dialog. None means cancelled."""
        win = tk.Toplevel(self.root)
        win.title('도면 출력 옵션')
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        frame = ttk.Frame(win, padding=18)
        frame.pack(fill='both', expand=True)
        vertical_var = tk.StringVar(value='400')
        split_var = tk.BooleanVar(value=False)
        split_length_var = tk.StringVar(value='700')
        datum_var = tk.BooleanVar(value=True)
        alignment_var = tk.StringVar(value=getattr(self, 'last_alignment_dxf', ''))
        profile_var = tk.BooleanVar(value=True)
        plan_var = tk.BooleanVar(value=bool(alignment_var.get()))
        ttk.Label(frame, text='종단 축척 (1:V)').grid(row=0, column=0, sticky='w', padx=(0, 14), pady=8)
        entry = ttk.Entry(frame, textvariable=vertical_var, width=17)
        entry.grid(row=0, column=1, sticky='ew', pady=8)
        ttk.Label(frame, text='종단 분할 옵션').grid(row=1, column=0, sticky='w', padx=(0, 14), pady=8)
        ttk.Checkbutton(frame, text='독립 DXF 분할', variable=split_var).grid(row=1, column=1, sticky='w', pady=8)
        ttk.Label(frame, text='분할 길이 (m)').grid(row=1, column=2, sticky='w', padx=(12,4))
        ttk.Entry(frame, textvariable=split_length_var, width=9).grid(row=1, column=3, sticky='w')
        ttk.Checkbutton(frame, text='Datum 표고 자동 적용 (종단 절단)', variable=datum_var).grid(row=2, column=0, columnspan=2, sticky='w', pady=(5, 3))
        ttk.Label(frame, text='해제 시: 기준 표고 고정 · 상한선 없음 · 종단 절단 없음', foreground='gray').grid(row=3, column=0, columnspan=2, sticky='w', pady=(0, 10))
        ttk.Checkbutton(frame, text='종평면도 출력 (final_result.dxf)', variable=profile_var).grid(row=4, column=0, columnspan=2, sticky='w')
        ttk.Checkbutton(frame, text='최종 평면도 출력 (final_plan_result.dxf)', variable=plan_var).grid(row=5, column=0, columnspan=2, sticky='w')
        buttons = ttk.Frame(frame)
        ttk.Label(frame, text='평면선형 DXF (원본)').grid(row=6, column=0, sticky='w', pady=6)
        ttk.Entry(frame, textvariable=alignment_var, width=42).grid(row=6, column=1, sticky='ew', pady=6)
        def browse_alignment():
            selected = filedialog.askopenfilename(parent=win, title='평면선형 DXF 선택',
                filetypes=[('DXF 도면', '*.dxf')])
            if selected:
                alignment_var.set(selected)
                plan_var.set(True)
        ttk.Button(frame, text='평면선형 DXF 찾아보기', command=browse_alignment).grid(row=7, column=0, columnspan=2, sticky='w', pady=(0,8))
        buttons.grid(row=8, column=0, columnspan=2, sticky='e')
        result = {'value': None}
        def accept():
            try:
                v = float(vertical_var.get().strip())
                if not math.isfinite(v) or v <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror('축척 입력 오류', '종단 축척은 0보다 큰 숫자여야 합니다.', parent=win)
                return
            if not profile_var.get() and not plan_var.get():
                messagebox.showerror('출력 옵션', '최소 한 종류의 출력을 선택하세요.', parent=win)
                return
            plan_path = alignment_var.get().strip()
            if plan_var.get() and (not plan_path or not Path(plan_path).is_file()):
                messagebox.showerror('평면선형 DXF', '최종 평면도 출력에는 유효한 평면선형 DXF가 필요합니다.', parent=win)
                return
            split_length = None
            if split_var.get() and profile_var.get():
                try:
                    split_length = float(split_length_var.get())
                    if not math.isfinite(split_length) or split_length <= 0:
                        raise ValueError
                except ValueError:
                    messagebox.showerror('분할 길이', '0보다 큰 분할 길이(m)를 입력하세요.', parent=win)
                    return
            self.last_alignment_dxf = plan_path
            result['value'] = (DrawingOptions(vertical_scale=v, auto_datum=datum_var.get(),
                horizontal_alignment_dxf=plan_path or None), profile_var.get(), plan_var.get(), split_length)
            win.destroy()
        ttk.Button(buttons, text='확인', command=accept, width=10).pack(side='left', padx=(0, 7))
        ttk.Button(buttons, text='취소', command=win.destroy, width=10).pack(side='left')
        win.protocol('WM_DELETE_WINDOW', win.destroy)
        win.bind('<Return>', lambda event: accept())
        win.bind('<Escape>', lambda event: win.destroy())
        win.update_idletasks()
        win.geometry(f'+{self.root.winfo_rootx()+80}+{self.root.winfo_rooty()+80}')
        entry.focus_set()
        self.root.wait_window(win)
        return result['value']

    def export_drawing(self):
        """Export selected drawing(s) independently, preserving both input DXFs."""
        if self.exporting:
            return
        if self.dxf_path is None or not self.last_vips or not self.last_stations:
            messagebox.showwarning('도면 출력', '먼저 DXF를 불러와 종단 분석을 완료하세요.')
            return
        choice = self._print_options()
        if choice is None:
            return
        drawing_options, export_profile, export_plan, split_length = choice
        source = self.dxf_path.resolve()
        plan_source = Path(drawing_options.horizontal_alignment_dxf).resolve() if drawing_options.horizontal_alignment_dxf else None
        if export_plan and plan_source == source:
            messagebox.showerror('도면 출력', '평면선형 원본과 종단 설계 DXF는 별도 파일이어야 합니다.')
            return
        directory = filedialog.askdirectory(title='DXF 출력 폴더 선택', initialdir=str(source.parent))
        if not directory:
            return
        folder = Path(directory).resolve()
        targets = []
        if export_profile:
            if split_length is None:
                targets.append(folder / 'final_result.dxf')
            else:
                from profile_split import sheet_ranges
                from profile_calculator import read_ground_points
                ground = read_ground_points(source)
                start = max(ground[0][0], self.last_vips[0].sta)
                end = min(ground[-1][0], self.last_vips[-1].sta)
                try:
                    ranges = sheet_ranges(start, end, split_length)
                except ValueError as exc:
                    messagebox.showerror('분할 범위', str(exc))
                    return
                targets.extend(folder / f'종단면도({i}).dxf' for i in range(1, len(ranges)+1))
        if export_plan:
            targets.append(folder / 'final_plan_result.dxf')
        if any(t.resolve() == source or (plan_source and t.resolve() == plan_source) for t in targets):
            messagebox.showerror('도면 출력', '출력 파일이 입력 원본과 충돌합니다. 다른 폴더를 선택하세요.')
            return
        existing = [str(t) for t in targets if t.exists()]
        if existing and not messagebox.askyesno('출력 파일 덮어쓰기',
                '다음 결과 파일을 덮어쓰시겠습니까?\n' + '\n'.join(existing) +
                '\n\nCAD에서 파일을 닫은 뒤 진행하세요.'):
            return
        self.exporting = True
        self.export_button.configure(state='disabled')
        self.status_var.set('도면 출력 중')
        self._log('DXF 출력 시작: ' + ', '.join(str(t) for t in targets))
        generation = self.generation
        # Snapshot the final analyzed VIP data so both outputs share the same design state.
        vips = tuple(self.last_vips)
        apply_vc = bool(self.vc_draw_var.get()) and export_profile
        try:
            vc_lengths_by_index = ({i: self.vc_lengths[p.sta]
                                    for i, p in enumerate(vips) if p.sta in self.vc_lengths
                                    and self.vc_lengths[p.sta] > 0} if apply_vc else {})
            if vc_lengths_by_index:
                VerticalAlignment([(p.sta, p.elevation) for p in vips], vc_lengths_by_index)
        except ValueError as exc:
            self.exporting = False
            self.export_button.configure(state='normal')
            messagebox.showerror('종곡선 출력 설정 오류', str(exc))
            return
        try:
            girder_settings = self.structure_editor.girder_settings() if export_profile else None
            pier_settings = self.structure_editor.pier_settings() if export_profile else None
            structures = tuple(self.structure_editor.segments) if (export_profile or export_plan) else ()
            bridge_layer_colors = self.structure_editor.bridge_layer_colors() if export_profile else None
            label_settings = self.structure_editor.label_settings() if export_profile else None
            plan_bridge_span = self.structure_editor.girder_settings().girder_length if export_plan else 30.0
            plan_bridge_section = self.structure_editor.bridge_plan_section() if export_plan else None
            plan_bridge_pier = self.structure_editor.plan_pier_settings() if export_plan else None
        except (ValueError, TypeError) as exc:
            self.exporting = False
            self.export_button.configure(state='normal')
            messagebox.showerror('거더 출력 설정 오류', str(exc))
            return
        def work():
            successes, failures = [], []
            if export_profile:
                try:
                    if split_length is None:
                        result = create_profile_drawing(source, folder / 'final_result.dxf', drawing_options,
                                                        vertical_curve_lengths=vc_lengths_by_index,
                                                        structures=structures, girder_settings=girder_settings, pier_settings=pier_settings, bridge_layer_colors=bridge_layer_colors, label_settings=label_settings)
                        successes.append(('종평면도', str(result['output']), len(vips)))
                    else:
                        from profile_split import export_split_profiles
                        results = export_split_profiles(source, folder, split_length, drawing_options, vc_lengths_by_index,
                                                        structures, girder_settings, pier_settings, bridge_layer_colors, label_settings)
                        successes.append((f'종평면도 {len(results)}장 분할', str(folder), len(vips)))
                except Exception as exc:
                    failures.append(('종평면도', str(exc)))
            if export_plan:
                try:
                    placed = create_final_plan(plan_source, source, folder / 'final_plan_result.dxf',
                                               vips=vips, structures=structures,
                                               bridge_nominal_span=plan_bridge_span,
                                               bridge_plan_section=plan_bridge_section,
                                               bridge_plan_pier_settings=plan_bridge_pier)
                    successes.append(('최종 평면도', str(folder / 'final_plan_result.dxf'), len(placed)))
                except Exception as exc:
                    failures.append(('최종 평면도', str(exc)))
            self.events.put((generation, 'export_summary', (successes, failures)))
        threading.Thread(target=work, daemon=True).start()

    def _export_summary(self, summary):
        successes, failures = summary
        self.exporting = False
        if self.last_vips:
            self.export_button.configure(state='normal')
        lines = [f'{name}: 저장 완료 (VIP {count}개)\n{path}' for name, path, count in successes]
        lines += [f'{name}: 실패 - {reason}' for name, reason in failures]
        for line in lines:
            self._log(line)
        self.status_var.set('도면 출력 완료' if not failures else '도면 출력 일부 실패' if successes else '도면 출력 실패')
        message = '\n\n'.join(lines)
        if failures:
            messagebox.showwarning('도면 출력 결과', message)
        else:
            messagebox.showinfo('도면 출력 완료', message)

    def show_manual(self):
        win = tk.Toplevel(self.root)
        win.title('사용자 매뉴얼')
        win.geometry('670x430')
        content = (
            '1. TXT 입력\n측점과 지반고를 공백으로 구분한 TXT를 불러옵니다.\n'
            'converted_dxf.dxf가 없을 때만 생성합니다. 기존 설계는 덮어쓰지 않습니다.\n\n'
            '2. CAD 종단 설계\nGROUND_PROFILE은 지반고입니다.\n'
            'PLAN_PROFILE 레이어에 열린 LWPOLYLINE 1개를 그립니다.\n'
            '모든 설계 좌표는 1:1 (X=측점 m, Y=표고 m)입니다.\n'
            '호(bulge) 및 종곡선 계산은 아직 지원하지 않습니다.\n\n'
            '3. 자동 계산\nCAD에서 DXF를 저장하면 VIP와 증분측점별 표고차를 계산하고 CSV를 갱신합니다.\n\n'
            '4. 도면 출력\n분석 완료 후 도면 출력 (DXF)을 눌러 최종 종단면도를 생성합니다.\n'
            '지반선, 계획선, 20m/200m 그리드, VIP 표기, 구배·거리, 하단 밴드를 포함합니다.\n'
            '출력 옵션에서 수직 축척(기본 1:400)을 설정할 수 있습니다. 도면 분할과 종곡선 종거값은 추후 지원합니다.\n'
            'converted_dxf.dxf는 항상 읽기 전용으로 취급합니다.'
        )
        text = tk.Text(win, wrap='word', padx=15, pady=12, font=('맑은 고딕', 10))
        text.insert('1.0', content)
        text.configure(state='disabled')
        text.pack(fill='both', expand=True)

    def close(self):
        self.closed = True
        self.stop_watch()
        self.root.destroy()


def main():
    root = RootClass()
    AlignmentGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
