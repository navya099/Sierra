"""v1.9-A.1: update existing title-block ATTRIB values without rebuilding blocks."""
from __future__ import annotations
import math


def format_station(sta: float) -> str:
    """0+000.00 style; keeps the station value accurate to 0.01 m."""
    sign = '-' if sta < 0 else ''
    centi = int(math.floor(abs(sta) * 100 + 0.5))
    km, remainder = divmod(centi, 100000)
    return f"{sign}{km}km{remainder / 100:06.2f}"


def format_scale(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:g}"


def update_titleblock(doc, *, number: int, total: int, sheet_start: float,
                      sheet_end: float, horizontal_scale: float,
                      vertical_scale: float, project_name: str | None = None,
                      route_name: str | None = None, drawing_title: str = '종평면도') -> dict:
    """Modify attributes on existing INSERT only; preserve text position/style and block geometry."""
    updates = {
        'TD_DWGNO': f'{number:03d} OF {total:03d}',
        'TB_STITL': f'{format_station(sheet_start)} ~ {format_station(sheet_end)}',
        'SCALE': f'H={format_scale(horizontal_scale)}, V={format_scale(vertical_scale)}',
        'TD_DNAME_MAIN': f'{drawing_title}({number})',
    }
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
