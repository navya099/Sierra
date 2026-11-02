"""Strict preset loader: immutable caller copies, no implicit fallback."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
from .schema import PresetKey

ROOT = Path(__file__).resolve().parent
MODES = frozenset({'cad', 'report'})
STANDARDS = frozenset({'detailed', 'simplified', 'overview'})
REQUIRED_LAYOUT = {
    'sheet': ('origin_x', 'origin_y', 'label_column_width', 'start_margin', 'end_margin'),
    'profile': ('plot_lower_y', 'plot_upper_y', 'datum_step_m', 'datum_safety_margin_m'),
    'band': ('alignment_height', 'ground_height', 'design_height', 'fill_height', 'cut_height', 'distance_rule_offset', 'grade_rule_offset'),
    'text': ('data_text_height', 'label_text_height', 'datum_text_height', 'vip_text_height', 'annotation_row_height'),
    'symbols': ('vip_circle_radius', 'datum_break_width', 'datum_break_height'),
    'stations': ('station_interval', 'major_interval', 'band_interval', 'alignment_station_interval'),
}
REQUIRED_VISIBILITY = ('minor_station_labels', 'vertical_curve_details', 'pier_details', 'datum_labels', 'alignment_band', 'ground_profile', 'design_profile')

def _number(value, field, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{field}: finite number required')
    if positive and value <= 0:
        raise ValueError(f'{field}: must be > 0')
    if not positive and value < 0:
        raise ValueError(f'{field}: must be >= 0')

def validate_preset(data, expected_mode=None, expected_scales=None):
    if not isinstance(data, dict):
        raise ValueError('preset must be an object')
    if data.get('schema_version') != 1 or isinstance(data.get('schema_version'), bool):
        raise ValueError('unsupported schema_version')
    if data.get('mode') not in MODES:
        raise ValueError('invalid mode')
    if data.get('standard_type') not in STANDARDS:
        raise ValueError('invalid standard_type')
    if not isinstance(data.get('name'), str) or not data['name'].strip():
        raise ValueError('name required')
    for key in ('horizontal_scale', 'vertical_scale'):
        v = data.get(key)
        _number(v, key, positive=True)
        if int(v) != v:
            raise ValueError(f'{key}: integer scale required')
    if expected_mode is not None and data['mode'] != expected_mode:
        raise ValueError('mode/file mismatch')
    if expected_scales is not None and (data['horizontal_scale'], data['vertical_scale']) != tuple(expected_scales):
        raise ValueError('scale/file mismatch')
    layout = data.get('layout')
    if not isinstance(layout, dict):
        raise ValueError('layout required')
    for group, fields in REQUIRED_LAYOUT.items():
        values = layout.get(group)
        if not isinstance(values, dict):
            raise ValueError(f'layout.{group} required')
        for field in fields:
            _number(values.get(field), f'layout.{group}.{field}', positive=(field not in ('origin_x', 'origin_y', 'start_margin', 'end_margin', 'datum_safety_margin_m')))
    profile = layout['profile']
    if profile['plot_upper_y'] <= profile['plot_lower_y']:
        raise ValueError('plot_upper_y must exceed plot_lower_y')
    placement = layout.get('placement')
    if placement is not None:
        if not isinstance(placement, dict) or type(placement.get('enabled')) is not bool:
            raise ValueError('layout.placement.enabled: boolean required')
        for key in ('band_to_profile_gap', 'reserved_structure_depth',
                    'structure_clearance', 'profile_plot_height', 'datum_label_offset'):
            _number(placement.get(key), f'layout.placement.{key}',
                    positive=(key == 'profile_plot_height'))
    visibility = data.get('visibility')
    if not isinstance(visibility, dict):
        raise ValueError('visibility required')
    for key in REQUIRED_VISIBILITY:
        if type(visibility.get(key)) is not bool:
            raise ValueError(f'visibility.{key}: boolean required')
    # S3-D4 policy is optional to preserve legacy user presets.
    policy = data.get('visibility_policy')
    if policy is not None:
        keys = ('enabled', 'minor_grid', 'vertical_curve_annotations',
                'vip_annotations', 'datum_labels', 'alignment_geometry',
                'ground_profile', 'design_profile', 'bridge_piers',
                'bridge_abutments', 'bridge_girders', 'structure_labels',
                'tunnel_portals', 'tunnel_bodies')
        if not isinstance(policy, dict) or set(policy) != set(keys):
            raise ValueError('visibility_policy: exact S3-D4 keys required')
        for key in keys:
            if type(policy[key]) is not bool:
                raise ValueError(f'visibility_policy.{key}: boolean required')
    if data.get('status') not in ('baseline', 'provisional'):
        raise ValueError('status must be baseline or provisional')
    return True

def load_preset(mode, horizontal_scale, vertical_scale, *, root=None):
    if mode not in MODES:
        raise ValueError('mode must be cad or report')
    for v in (horizontal_scale, vertical_scale):
        _number(v, 'scale', positive=True)
        if int(v) != v:
            raise ValueError('integer scale required')
    key = PresetKey(mode, int(horizontal_scale), int(vertical_scale))
    base = Path(root) if root is not None else ROOT
    path = base / mode / key.filename
    if not path.is_file():
        raise FileNotFoundError(f'preset not found: {mode}/{key.filename}')
    with path.open(encoding='utf-8') as f:
        data = json.load(f)
    validate_preset(data, expected_mode=mode, expected_scales=(horizontal_scale, vertical_scale))
    return copy.deepcopy(data)

def list_presets(*, root=None):
    base = Path(root) if root is not None else ROOT
    items = []
    for mode in ('cad', 'report'):
        for path in sorted((base / mode).glob('h*_v*.json')):
            with path.open(encoding='utf-8') as f:
                data = json.load(f)
            validate_preset(data, expected_mode=mode)
            if path.name != PresetKey(mode, int(data['horizontal_scale']), int(data['vertical_scale'])).filename:
                raise ValueError(f'filename mismatch: {path}')
            items.append({'mode': mode, 'name': data['name'], 'horizontal_scale': data['horizontal_scale'], 'vertical_scale': data['vertical_scale'], 'standard_type': data['standard_type'], 'status': data['status']})
    return items
