"""Sierra combined plan/profile GUI adapter (G1-2B).

Copy this file to combined_plan_profile/gui.py.
The existing CLI generator remains unchanged.
"""
from __future__ import annotations

import json
from dataclasses import asdict
import math
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class CombinedPlanProfileWindow(tk.Toplevel):
    def __init__(self, parent, owner=None):
        super().__init__(parent)
        self.owner = owner
        self.title('종평면도 생성')
        self.geometry('900x730')
        self.minsize(760, 620)
        self.events = queue.Queue()
        self.process = None
        self.running = False
        self._closing = False
        self.vars = {
            'plan': tk.StringVar(value=str(getattr(owner, 'last_alignment_dxf', '') or '')),
            'profile': tk.StringVar(value=str(getattr(owner, 'dxf_path', '') or '')),
            'output_dir': tk.StringVar(),
            'template': tk.StringVar(),
            'titleblock_config': tk.StringVar(),
            'structures_csv': tk.StringVar(),
            'structure_settings_json': tk.StringVar(),
            'structure_label_preset': tk.StringVar(),
            'sheet_length': tk.StringVar(value='700'),
            'horizontal_scale': tk.StringVar(value='1000'),
            'vertical_scale': tk.StringVar(value='400'),
            'station_origin': tk.StringVar(value='0'),
            'start_sta': tk.StringVar(),
            'end_sta': tk.StringVar(),
            'project_name': tk.StringVar(),
            'route_name': tk.StringVar(),
            'left_direction': tk.StringVar(value='서울쪽'),
            'right_direction': tk.StringVar(value='부산쪽'),
        }
        self.use_vc = tk.BooleanVar(value=bool(getattr(owner, 'vc_lengths', {})))
        editor = getattr(owner, 'structure_editor', None)
        self.use_structures = tk.BooleanVar(value=bool(getattr(editor, 'segments', [])))
        self.use_structure_settings = tk.BooleanVar(value=bool(getattr(editor, 'segments', [])))
        self._build()
        self.protocol('WM_DELETE_WINDOW', self._close)
        self.after(100, self._poll)

    def _build(self):
        container = ttk.Frame(self, padding=12)
        container.pack(fill='both', expand=True)
        inputs = ttk.LabelFrame(container, text='도면 및 출력 설정', padding=10)
        inputs.pack(fill='x')
        rows = [
            ('plan', '평면선형 DXF', 'file', [('DXF', '*.dxf')]),
            ('profile', '종단선형 DXF', 'file', [('DXF', '*.dxf')]),
            ('output_dir', '출력 폴더', 'dir', None),
            ('template', '도곽 DXF (선택)', 'file', [('DXF', '*.dxf')]),
            ('titleblock_config', '도곽 설정 JSON (선택)', 'file', [('JSON', '*.json')]),
            ('structures_csv', '구조물 CSV (선택)', 'file', [('CSV', '*.csv')]),
            ('structure_settings_json', '구조물 설정 JSON (선택)', 'file', [('JSON', '*.json')]),
            ('structure_label_preset', 'S3-D9 구조물 주석 프리셋 (비우면 축척별 내장)', 'file', [('JSON', '*.json')]),
        ]
        for r, (key, title, kind, types) in enumerate(rows):
            ttk.Label(inputs, text=title).grid(row=r, column=0, sticky='w', pady=3)
            ttk.Entry(inputs, textvariable=self.vars[key]).grid(row=r, column=1, sticky='ew', padx=7)
            ttk.Button(inputs, text='찾아보기', command=lambda k=key, m=kind, t=types: self._browse(k, m, t)).grid(row=r, column=2)
        inputs.columnconfigure(1, weight=1)
        options = ttk.LabelFrame(container, text='측점 및 축척', padding=10)
        options.pack(fill='x', pady=8)
        opts = [
            ('sheet_length', '시트 길이 (m)'), ('horizontal_scale', '수평 축척 (1:H)'),
            ('vertical_scale', '수직 축척 (1:V)'), ('station_origin', '평면 측점 원점 (m)'),
            ('start_sta', '시작 측점 (선택)'), ('end_sta', '종료 측점 (선택)'),
            ('project_name', '사업명 (선택)'), ('route_name', '노선명 (선택)'),
            ('left_direction', '좌측 방향'), ('right_direction', '우측 방향'),
        ]
        for i, (key, label) in enumerate(opts):
            r, c = divmod(i, 2)
            c *= 2
            ttk.Label(options, text=label).grid(row=r, column=c, sticky='w', pady=3)
            ttk.Entry(options, textvariable=self.vars[key], width=20).grid(row=r, column=c+1, sticky='ew', padx=(6, 12))
        options.columnconfigure(1, weight=1)
        options.columnconfigure(3, weight=1)
        ttk.Checkbutton(container, text='현재 GUI 종곡선 설정 적용 (측점 JSON)', variable=self.use_vc).pack(anchor='w', pady=3)
        ttk.Checkbutton(container, text='현재 구조물 편집기 목록 자동 적용 (수동 CSV보다 우선)', variable=self.use_structures).pack(anchor='w', pady=3)
        ttk.Checkbutton(container, text='현재 구조물 편집기 상세 설정 자동 적용 (수동 JSON보다 우선)', variable=self.use_structure_settings).pack(anchor='w', pady=3)
        actions = ttk.Frame(container)
        actions.pack(fill='x', pady=5)
        ttk.Button(actions, text='실행 명령 미리보기', command=self._preview).pack(side='left', padx=(0, 8))
        self.run_button = ttk.Button(actions, text='종평면도 생성', command=self._start)
        self.run_button.pack(side='left')
        ttk.Button(actions, text='닫기', command=self._close).pack(side='right')
        log_frame = ttk.LabelFrame(container, text='실행 로그', padding=5)
        log_frame.pack(fill='both', expand=True)
        self.log = tk.Text(log_frame, height=10, wrap='word', state='disabled')
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def _browse(self, key, kind, types):
        if kind == 'dir':
            value = filedialog.askdirectory(parent=self)
        else:
            value = filedialog.askopenfilename(parent=self, filetypes=types)
        if value:
            self.vars[key].set(value)

    def _values(self):
        values = {k: v.get().strip() for k, v in self.vars.items()}
        for key in ('plan', 'profile'):
            if not values[key] or not Path(values[key]).is_file():
                raise ValueError(f'{key}: 유효한 DXF 파일을 선택하세요.')
        if Path(values['plan']).resolve() == Path(values['profile']).resolve():
            raise ValueError('평면 DXF와 종단 DXF는 서로 다른 파일이어야 합니다.')
        for key in ('template', 'titleblock_config', 'structures_csv', 'structure_settings_json', 'structure_label_preset'):
            if values[key] and not Path(values[key]).is_file():
                raise ValueError(f'{key}: 선택한 파일이 없습니다.')
        if values['structure_settings_json'] and not values['structures_csv'] and not self.use_structures.get():
            raise ValueError('구조물 설정 JSON을 사용하려면 구조물 CSV도 지정하세요.')
        if not values['output_dir']:
            raise ValueError('출력 폴더를 선택하세요.')
        folder = Path(values['output_dir']).resolve()
        if folder.exists() and not folder.is_dir():
            raise ValueError('출력 경로가 폴더가 아닙니다.')
        for key in ('plan', 'profile', 'template', 'titleblock_config', 'structures_csv', 'structure_settings_json', 'structure_label_preset'):
            if values[key] and Path(values[key]).resolve().parent == folder:
                # Input files in the output directory are allowed; output names are checked by engine.
                pass
        for key in ('sheet_length', 'horizontal_scale', 'vertical_scale'):
            x = float(values[key])
            if not math.isfinite(x) or x <= 0:
                raise ValueError(f'{key}: 0보다 큰 유한한 숫자여야 합니다.')
        for key in ('station_origin', 'start_sta', 'end_sta'):
            if values[key] and not math.isfinite(float(values[key])):
                raise ValueError(f'{key}: 유한한 숫자여야 합니다.')
        if values['start_sta'] and values['end_sta'] and float(values['start_sta']) >= float(values['end_sta']):
            raise ValueError('종료 측점은 시작 측점보다 커야 합니다.')
        # Validate before launching subprocess, using the same strict S3-D9 loader.
        if values['structure_label_preset']:
            from profile_presets.loader import load_preset_file
            load_preset_file(values['structure_label_preset'], expected_mode='cad',
                             expected_scales=(float(values['horizontal_scale']), float(values['vertical_scale'])))
        vc = {}
        if self.use_vc.get():
            if self.owner is None:
                raise ValueError('종곡선 정보를 제공할 메인 GUI가 없습니다.')
            for sta, length in dict(getattr(self.owner, 'vc_lengths', {})).items():
                a, b = float(sta), float(length)
                if not math.isfinite(a) or not math.isfinite(b) or b < 0:
                    raise ValueError('종곡선 측점/길이 값이 올바르지 않습니다.')
                if b > 0:
                    vc[str(a)] = b
        segments = None
        if self.use_structures.get():
            editor = getattr(self.owner, 'structure_editor', None)
            if editor is None:
                raise ValueError('구조물 편집기를 찾을 수 없습니다.')
            segments = list(editor.segments)
            if not segments:
                raise ValueError('구조물 자동 적용이 선택되었지만 현재 구조물 목록이 비어 있습니다.')
            # Auto CSV supersedes the manually selected CSV, but does not change the GUI field.
            values['structures_csv'] = ''
        settings = None
        if self.use_structure_settings.get():
            editor = getattr(self.owner, 'structure_editor', None)
            if editor is None:
                raise ValueError('구조물 상세 설정을 제공할 편집기가 없습니다.')
            if segments is None and not values['structures_csv']:
                raise ValueError('구조물 상세 설정 자동 적용에는 구조물 목록 또는 수동 CSV가 필요합니다.')
            # Validate and snapshot Tk variables on the main GUI thread.
            girder = editor.girder_settings()
            pier = editor.pier_settings()
            label = editor.label_settings()
            plan_label = editor.plan_label_settings()
            tunnel = editor.tunnel_settings()
            if tunnel.portal is None:
                raise ValueError('현재 엔진의 설정 JSON 로더는 갱문 비활성화를 지원하지 않습니다. 자동 설정을 해제하고 수동 JSON을 사용하거나 갱문을 활성화하세요.')
            # G1-2C-4: reuse the existing bridge GUI abutment template.
            # The editor method resolves an empty selection to its built-in DXF.
            abutment_path = Path(editor.bridge_abutment_plan_path()).resolve()
            if not abutment_path.is_file():
                raise ValueError(f'교대 평면 템플릿 DXF 파일이 없습니다: {abutment_path}')
            # G1-2D-1: capture the validated bridge plan section and pier
            # dimensions from the existing StructureEditor. asdict() converts
            # the immutable section tuple data into JSON-compatible lists.
            plan_section = editor.bridge_plan_section()
            plan_section.validate()
            plan_pier = editor.plan_pier_settings()
            # G1-2D-2: preserve the main GUI's portal options, while making
            # custom DXF paths independent of the subprocess working directory.
            portal_config = asdict(tunnel.portal)
            for portal_key, portal_label in (
                ('custom_dxf', '종단 갱문'),
                ('plan_custom_dxf', '평면 갱문'),
            ):
                custom_path = str(portal_config.get(portal_key) or '').strip()
                if custom_path:
                    resolved = Path(custom_path).resolve()
                    if not resolved.is_file():
                        raise ValueError(f'사용자 지정 {portal_label} DXF 파일이 없습니다: {resolved}')
                    portal_config[portal_key] = str(resolved)
            settings = {
                'plan': {
                    'bridge_abutment_plan_dxf': str(abutment_path),
                    'bridge_section': asdict(plan_section),
                    'pier': asdict(plan_pier),
                    'labels_enabled': plan_label is not None,
                    'label': asdict(plan_label) if plan_label is not None else {},
                },
                'girder': asdict(girder),
                'pier': asdict(pier),
                'label': asdict(label),
                'bridge_layer_colors': editor.bridge_layer_colors(),
                'tunnel': {
                    'bottom_offset': tunnel.bottom_offset,
                    'body_height': tunnel.body_height,
                    'sample_step': tunnel.sample_step,
                    'color': tunnel.color,
                    'lining_thickness': tunnel.lining_thickness,
                },
                'portal': portal_config,
            }
            if editor.tunnel_section_mode.get() == 'dxf':
                section_path = editor.tunnel_section_path.get().strip()
                if not section_path or not Path(section_path).is_file():
                    raise ValueError('사용자 터널 단면 DXF 경로를 확인하세요.')
                settings['tunnel']['section_dxf'] = str(Path(section_path).resolve())
            values['structure_settings_json'] = ''
        return values, vc, segments, settings

    @staticmethod
    def _command(values, vc_json=None):
        cmd = [sys.executable, '-u', '-m', 'combined_plan_profile.combined_plan_profile_v1_8a']
        fields = [
            'plan', 'profile', 'output_dir', 'template', 'titleblock_config',
            'structures_csv', 'structure_settings_json', 'structure_label_preset', 'sheet_length',
            'horizontal_scale', 'vertical_scale', 'station_origin', 'start_sta',
            'end_sta', 'project_name', 'route_name', 'left_direction', 'right_direction',
        ]
        for key in fields:
            if values[key]:
                cmd.extend(['--' + key.replace('_', '-'), values[key]])
        if vc_json:
            cmd.extend(['--vertical-curve-sta-json', str(vc_json)])
        return cmd

    def _append(self, line):
        self.log.configure(state='normal')
        self.log.insert('end', line.rstrip('\n') + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _preview(self):
        try:
            values, vc, segments, settings = self._values()
            if segments is not None:
                values['structures_csv'] = '<현재 GUI 구조물 CSV>'
            if settings is not None:
                values['structure_settings_json'] = '<현재 GUI 구조물 설정 JSON>'
            command = self._command(values, '<현재 GUI 종곡선 JSON>' if vc else None)
            self._append(subprocess.list2cmdline(command))
        except (ValueError, OSError) as exc:
            messagebox.showerror('입력 오류', str(exc), parent=self)

    def _start(self):
        if self.running:
            return
        try:
            values, vc, segments, settings = self._values()
        except (ValueError, OSError) as exc:
            messagebox.showerror('입력 오류', str(exc), parent=self)
            return
        folder = Path(values['output_dir']).resolve()
        if folder.exists() and list(folder.glob('종평면도(*).dxf')):
            if not messagebox.askyesno('기존 결과 확인', '출력 폴더에 기존 종평면도 DXF가 있습니다. 계속하시겠습니까? CAD에서 파일을 닫아주세요.', parent=self):
                return
        self.running = True
        self.run_button.configure(state='disabled')
        self._append('종평면도 생성 시작')
        threading.Thread(target=self._worker, args=(values, vc, segments, settings), daemon=True).start()

    def _worker(self, values, vc, segments, settings):
        try:
            with tempfile.TemporaryDirectory(prefix='sierra_combined_') as tempdir:
                vc_path = None
                if vc:
                    vc_path = Path(tempdir) / 'vertical_curves.json'
                    vc_path.write_text(json.dumps(vc, ensure_ascii=False, indent=2), encoding='utf-8')
                if segments is not None:
                    from structure_engine import export_csv
                    structure_path = Path(tempdir) / 'structure_segments.csv'
                    export_csv(segments, structure_path)
                    values['structures_csv'] = str(structure_path)
                    self.events.put(('log', f'[G1-2C-2] 구조물 {len(segments)}개 자동 연동 (임시 CSV)'))
                if settings is not None:
                    settings_path = Path(tempdir) / 'structure_settings.json'
                    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
                    values['structure_settings_json'] = str(settings_path)
                    self.events.put(('log', '[G1-2D-2] 구조물 상세 설정·교대/터널 DXF 자동 연동 (임시 JSON)'))
                cmd = self._command(values, vc_path)
                Path(values['output_dir']).mkdir(parents=True, exist_ok=True)
                self.events.put(('log', subprocess.list2cmdline(cmd)))
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding='utf-8', errors='replace', bufsize=1,
                                        cwd=str(Path(__file__).resolve().parent.parent))
                self.process = proc
                for line in proc.stdout:
                    self.events.put(('log', line))
                code = proc.wait()
                self.events.put(('done', code))
        except Exception as exc:
            self.events.put(('error', str(exc)))
        finally:
            self.process = None

    def _poll(self):
        if self._closing:
            return
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self._append(value)
                elif kind == 'done':
                    self.running = False
                    self.run_button.configure(state='normal')
                    self._append('생성 완료 (종료 코드 0)' if value == 0 else f'생성 실패 (종료 코드 {value})')
                elif kind == 'error':
                    self.running = False
                    self.run_button.configure(state='normal')
                    self._append('실행 오류: ' + value)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _close(self):
        if self.running:
            messagebox.showwarning('생성 중', '도면 생성이 진행 중입니다. 완료 후 창을 닫아주세요.', parent=self)
            return
        self._closing = True
        self.destroy()


def open_combined_plan_profile_gui(parent, owner=None):
    return CombinedPlanProfileWindow(parent, owner)
