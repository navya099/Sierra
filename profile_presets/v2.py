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

ALIGNMENT_TEXT_FIELDS = ('station_height', 'station_top_inset', 'station_rotation',
                         'curve_info_height', 'curve_info_left_y', 'curve_info_right_y',
                         'curve_info_line_spacing', 'element_station_height',
                         'element_station_offset', 'element_station_x_offset')

def validate_layout_v2(layout):
    _object(layout, LAYOUT_FIELDS, 'layout')
    # S3-D7: alignment group is optional for older S3-D6 v2 presets.
    # When present, it is the sole source of alignment text dimensions.
    band = layout['band']
    if 'alignment' in band:
        _object(band['alignment'], ('diagram', 'text'), 'layout.band.alignment')
        _object(band['alignment']['diagram'], ('baseline_offset', 'curve_offset') if 'curve_offset' in band['alignment']['diagram'] else ('baseline_offset',), 'layout.band.alignment.diagram')
        text_fields = ALIGNMENT_TEXT_FIELDS + (('element_station',) if 'element_station' in band['alignment']['text'] else ())
        _object(band['alignment']['text'], text_fields, 'layout.band.alignment.text')
        if 'element_station' in band['alignment']['text']:
            element = band['alignment']['text']['element_station']
            _object(element, ('placement',), 'layout.band.alignment.text.element_station')
            placements = element['placement']
            if not isinstance(placements, dict) or not set(placements) <= {'SP','PC','CP','PS','BC','EC'}:
                raise ValueError('element_station.placement: invalid element names')
            for name, placement in placements.items():
                _object(placement, ('align','x_offset'), 'element_station.placement.'+name)
                if placement['align'] not in ('LEFT','CENTER','RIGHT'):
                    raise ValueError('element_station.placement.'+name+'.align: invalid')
                x = placement['x_offset']
                if type(x) not in (int,float) or not math.isfinite(x):
                    raise ValueError('element_station.placement.'+name+'.x_offset: finite number required')
        _num(band['alignment']['diagram']['baseline_offset'], 'layout.band.alignment.diagram.baseline_offset', allow_zero=True)
        if 'curve_offset' in band['alignment']['diagram']:
            _num(band['alignment']['diagram']['curve_offset'], 'layout.band.alignment.diagram.curve_offset', allow_zero=True)
        for key, value in band['alignment']['text'].items():
            if key == 'element_station':
                continue
            _num(value, 'layout.band.alignment.text.'+key, allow_zero=(key in
                 ('station_top_inset','station_rotation','curve_info_left_y',
                  'curve_info_right_y','element_station_offset','element_station_x_offset')))
        if band['alignment']['text']['station_rotation'] > 360:
            raise ValueError('layout.band.alignment.text.station_rotation: must be <= 360')
    for group, subgroups in LAYOUT_FIELDS.items():
        expected_groups = tuple(subgroups) + (('alignment',) if group == 'band' and 'alignment' in layout[group] else ())
        if group == 'annotations' and 'alignment' in layout['band']:
            expected_groups = tuple(k for k in expected_groups if k != 'alignment') if 'alignment' not in layout[group] else expected_groups
        _object(layout[group], expected_groups, f'layout.{group}')
        for subgroup, keys in subgroups.items():
            if group == 'annotations' and subgroup == 'alignment' and 'alignment' in layout['band'] and subgroup not in layout[group]:
                continue
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
