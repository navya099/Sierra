"""B.8: read the existing StructureEditor CSV and optional drawing settings JSON."""
from dataclasses import dataclass
from pathlib import Path
import csv
import json
import math
from .profile_engine.bridge_girder import GirderSettings
from .profile_engine.bridge_pier import PierSettings
from .profile_engine.structure_label import LabelSettings
from .profile_engine.tunnel_profile import TunnelSettings
from .profile_engine.tunnel_portal import PortalSettings
from .profile_engine.tunnel_section import load_tunnel_section

@dataclass(frozen=True)
class StructureSegment:
    kind: str
    start_sta: float
    end_sta: float
    max_height: float = 0.0
    peak_sta: float = 0.0
    source: str = 'MANUAL'
    name: str = ''
    @property
    def length(self):
        return self.end_sta - self.start_sta

def load_structures(path):
    result=[]
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f)
        required={'kind','start_sta','end_sta'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError('구조물 CSV 필수 열: kind, start_sta, end_sta')
        for line,row in enumerate(reader,2):
            kind=(row['kind'] or '').strip().upper()
            if kind not in ('BRIDGE','TUNNEL'):
                raise ValueError(f'{line}행: 구조물 유형은 BRIDGE 또는 TUNNEL')
            a,b=float(row['start_sta']),float(row['end_sta'])
            h=float(row.get('max_height') or 0)
            peak=float(row.get('peak_sta') or a)
            if not all(math.isfinite(x) for x in (a,b,h,peak)) or b<=a:
                raise ValueError(f'{line}행: 구조물 측점/수치 오류')
            result.append(StructureSegment(kind,a,b,h,peak,(row.get('source') or 'MANUAL').strip(),(row.get('name') or '').strip()))
    return result

def load_drawing_settings(path):
    config=json.loads(Path(path).read_text(encoding='utf-8')) if path else {}
    if not isinstance(config,dict):
        raise ValueError('구조물 설정 JSON은 객체여야 합니다.')
    allowed={'girder','pier','label','tunnel','portal','bridge_layer_colors','plan'}
    extra=set(config)-allowed
    if extra: raise ValueError(f'지원하지 않는 구조물 설정: {sorted(extra)}')
    def values(key):
        d=config.get(key,{})
        if not isinstance(d,dict): raise ValueError(f'{key} 설정은 객체여야 합니다.')
        return d
    girder=GirderSettings(**values('girder'));girder.validate()
    pier=PierSettings(**values('pier'));pier.validate()
    label=LabelSettings(**values('label'));label.validate()
    td=values('tunnel').copy()
    if 'section_dxf' in td:
        td['section']=load_tunnel_section(td.pop('section_dxf'))
    portal_values=values('portal')
    if portal_values or 'portal' in config:
        td['portal']=PortalSettings(**portal_values) if portal_values is not None else None
    else:
        td['portal']=PortalSettings()  # existing GUI default: portal enabled
    tunnel=TunnelSettings(**td);tunnel.validate()
    colors=config.get('bridge_layer_colors',{})
    if not isinstance(colors,dict):raise ValueError('bridge_layer_colors는 객체여야 합니다.')
    for name,value in colors.items():
        if name not in ('BRIDGE_GIRDER','BRIDGE_ABUTMENT','BRIDGE_PIER') or type(value) is not int or not 1<=value<=255:
            raise ValueError(f'잘못된 교량 레이어 색상: {name}={value}')
    return dict(girder_settings=girder,pier_settings=pier,label_settings=label,tunnel_settings=tunnel,bridge_layer_colors=colors)
