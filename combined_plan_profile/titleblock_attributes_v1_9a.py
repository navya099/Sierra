"""v1.9-A.1: update existing title-block ATTRIB values without rebuilding blocks."""
from __future__ import annotations
import math
import json
from pathlib import Path


def format_station(sta: float) -> str:
    """0+000.00 style; keeps the station value accurate to 0.01 m."""
    sign = '-' if sta < 0 else ''
    centi = int(math.floor(abs(sta) * 100 + 0.5))
    km, remainder = divmod(centi, 100000)
    return f"{sign}{km}km{remainder / 100:06.2f}"


def format_scale(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:g}"


AUTO_TAGS = frozenset({'TD_DWGNO', 'TB_STITL', 'SCALE', 'TD_DNAME_MAIN'})


def load_titleblock_config(path):
    """Read user-editable JSON; suitable for future GUI serialization."""
    if path is None:
        return {'attributes': {}, 'drawing_title': '종평면도'}
    with Path(path).open('r', encoding='utf-8-sig') as f:
        config = json.load(f)
    if not isinstance(config, dict):
        raise ValueError('JSON 최상위는 객체여야 합니다.')
    if set(config) - {'attributes', 'drawing_title'}:
        raise ValueError('알 수 없는 JSON 설정 키가 있습니다.')
    raw = config.get('attributes', {})
    if not isinstance(raw, dict):
        raise ValueError('attributes는 태그:문자열 객체여야 합니다.')
    attrs = {}
    for tag, value in raw.items():
        if not isinstance(tag, str) or not tag.strip():
            raise ValueError('속성 태그는 비어 있지 않은 문자열이어야 합니다.')
        key = tag.strip().upper()
        if key in AUTO_TAGS:
            raise ValueError(f'시트별 자동 속성은 JSON으로 덮어쓸 수 없습니다: {key}')
        if value is None:
            continue  # preserve original template value
        if not isinstance(value, str):
            raise ValueError(f'{key}: 값은 문자열 또는 null이어야 합니다.')
        if key in attrs:
            raise ValueError(f'중복 속성 태그: {key}')
        attrs[key] = value
    title = config.get('drawing_title', '종평면도')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('drawing_title은 비어 있지 않은 문자열이어야 합니다.')
    return {'attributes': attrs, 'drawing_title': title}


def update_titleblock(doc, *, number: int, total: int, sheet_start: float,
                      sheet_end: float, horizontal_scale: float,
                      vertical_scale: float, project_name: str | None = None,
                      route_name: str | None = None, drawing_title: str = '종평면도',
                      custom_attributes: dict | None = None) -> dict:
    """Modify attributes on existing INSERT only; preserve text position/style and block geometry."""
    updates = {
        'TD_DWGNO': f'{number:03d} OF {total:03d}',
        'TB_STITL': f'{format_station(sheet_start)} ~ {format_station(sheet_end)}',
        'SCALE': f'H={format_scale(horizontal_scale)}, V={format_scale(vertical_scale)}',
        'TD_DNAME_MAIN': f'{drawing_title}({number})',
    }
    if custom_attributes:
        for tag, value in custom_attributes.items():
            key = tag.upper()
            if key in AUTO_TAGS:
                raise ValueError(f'자동 속성 변경 금지: {key}')
            updates[key] = value
    if project_name is not None:
        updates['TD_CNAME'] = project_name
    if route_name is not None:
        updates['TD_RLNAME'] = route_name
    counts = {tag: 0 for tag in updates}
    for insert in doc.modelspace().query('INSERT'):
        for attr in insert.attribs:
            tag = attr.dxf.tag.upper()
            if tag in updates:
                attr.dxf.text = updates[tag]
                counts[tag] += 1
    missing = [tag for tag, n in counts.items() if n == 0]
    if missing:
        raise ValueError(f'도각 속성 태그가 없습니다: {missing}. --template 도각 DXF를 확인하세요.')
    return counts
