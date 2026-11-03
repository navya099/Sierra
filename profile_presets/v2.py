"""S3-D6 nested absolute-dimension preset (schema v2) validation."""
import math

LAYOUT_FIELDS = {
    'sheet': {'origin': ('x','y'), 'margin': ('start','end'), 'drawing_limits': ('plot_lower_y','plot_upper_y')},
    'band': {'column': ('label_width',), 'height': ('alignment','ground','design','fill','cut'), 'text': ('data_height','label_height')},
    'profile': {'plot': ('height',), 'datum': ('step_m','safety_margin_m','text_height'), 'clearance': ('band_to_profile_gap','reserved_structure_depth','structure_clearance','use_placement_clearance')},
    'stations': {'grid': ('sub_interval','main_interval'), 'text': ('band_interval','alignment_station_interval')},
    'symbols': {'vip': ('circle_radius',), 'datum': ('break_width','break_height')},
    'annotations': {'datum': ('label_dx','label_dy','break_kink_dy'), 'alignment': ('station_top_inset',),
                    'vip': ('text_height','elevation_text_height','caption_text_height','caption_gap_factor','distance_text_offset','distance_text_height','arrow_half_height','arrow_length','rule'),
                    'vertical_curve': ('ordinate_offset','endpoint_text_offset','endpoint_line_height','text_height'),
                    'grade': ('text_height',), 'distance': ('text_height',), 'row': ('height',)}
}

def _object(value, expected, path):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f'{path}: expected keys {sorted(expected)}')

def _num(value, path, allow_zero=False):
    if type(value) not in (int,float) or not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
        raise ValueError(f'{path}: finite {"nonnegative" if allow_zero else "positive"} number required')

def validate_layout_v2(layout):
    _object(layout, LAYOUT_FIELDS, 'layout')
    for group, subgroups in LAYOUT_FIELDS.items():
        _object(layout[group], subgroups, f'layout.{group}')
        for subgroup, keys in subgroups.items():
            values = layout[group][subgroup]
            path = f'layout.{group}.{subgroup}'
            _object(values, keys, path)
            for key in keys:
                if key == 'rule' and path == 'layout.annotations.vip':
                    rule = values[key]
                    _object(rule, ('distance_offset','grade_offset'), path+'.rule')
                    for name, value in rule.items():
                        _num(value, path+'.rule.'+name)
                elif key == 'use_placement_clearance':
                    if type(values[key]) is not bool:
                        raise ValueError(path+'.'+key+': boolean required')
                else:
                    allow_zero = (path == 'layout.sheet.origin' or
                                  (path == 'layout.sheet.margin') or
                                  (path == 'layout.sheet.drawing_limits' and key == 'plot_lower_y') or
                                  (path == 'layout.profile.datum' and key == 'safety_margin_m') or
                                  (path == 'layout.profile.clearance' and key != 'use_placement_clearance'))
                    _num(values[key], path+'.'+key, allow_zero=allow_zero)
    limits = layout['sheet']['drawing_limits']
    if limits['plot_upper_y'] <= limits['plot_lower_y']:
        raise ValueError('layout.sheet.drawing_limits: upper must exceed lower')
    return True
