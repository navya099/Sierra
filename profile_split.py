"""Independent DXF sheet export; never modifies the design source."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import math

from dxf_reader import extract_profile
from profile_calculator import read_ground_points
from profile_drawing import DrawingOptions, create_profile_drawing

def sheet_ranges(start: float, end: float, length: float) -> list[tuple[float, float]]:
    if not all(math.isfinite(x) for x in (start, end, length)) or length <= 0 or end <= start:
        raise ValueError('분할 길이는 양수, 측점 범위는 시작 < 종료여야 합니다.')
    n = math.ceil((end-start)/length - 1e-10)
    if n > 10000:
        raise ValueError('분할 도면이 10,000장을 초과합니다.')
    result = []
    for i in range(n):
        a = start + i*length
        b = end if i == n-1 else min(end, start+(i+1)*length)
        if b > a + 1e-8:
            result.append((a,b))
    return result

def export_split_profiles(source_dxf, output_folder, length, options=None, vertical_curve_lengths=None, structures=None, girder_settings=None, pier_settings=None, bridge_layer_colors=None):
    source = Path(source_dxf).resolve()
    ground = read_ground_points(source)
    vip = extract_profile(source)
    start = max(ground[0][0], vip[0].sta)
    end = min(ground[-1][0], vip[-1].sta)
    ranges = sheet_ranges(start, end, float(length))
    folder = Path(output_folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    opts = options or DrawingOptions()
    results = []
    for i, (a,b) in enumerate(ranges, 1):
        output = folder / f'종단면도({i}).dxf'
        local = replace(opts, sheet_start_sta=a, sheet_end_sta=b)
        results.append(create_profile_drawing(source, output, local, vertical_curve_lengths, structures, girder_settings, pier_settings, bridge_layer_colors))
    return results
