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
            _object(element, ('placement', 'y_offset') if 'y_offset' in element else ('placement',), 'layout.band.alignment.text.element_station')
            if 'y_offset' in element:
                offsets = element['y_offset']
                _object(offsets, ('LEFT', 'RIGHT'), 'layout.band.alignment.text.element_station.y_offset')
                for direction, value in offsets.items():
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError('element_station.y_offset.' + direction + ': finite number required')
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
    # S3-D8.2: optional scale-dependent profile structure-label dimensions.
    structure = layout['annotations'].get('structure_label')
    if structure is not None:
        _object(structure, ('text', 'leader'), 'layout.annotations.structure_label')
        text_cfg = structure['text']
        required_text = ('height', 'color', 'rotation')
        optional_text = ('title_offset_factor', 'station_offset_factor', 'title', 'station')
        if not isinstance(text_cfg, dict) or any(k not in text_cfg for k in required_text) or any(k not in required_text + optional_text for k in text_cfg):
            raise ValueError('layout.annotations.structure_label.text: invalid keys')
        for label in ('title', 'station'):
            if label in text_cfg:
                _object(text_cfg[label], ('x_offset', 'y_offset'), 'layout.annotations.structure_label.text.' + label)
                for axis in ('x_offset', 'y_offset'):
                    value = text_cfg[label][axis]
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError('structure_label.text.' + label + '.' + axis + ': finite number required')
        _object(structure['leader'], ('vertical_height', 'angle', 'margin'), 'layout.annotations.structure_label.leader')
        for key in ('height',):
            _num(structure['text'][key], 'structure_label.text.'+key)
        for key in ('vertical_height', 'margin'):
            _num(structure['leader'][key], 'structure_label.leader.'+key)
        for group_name, keys in (('text', ('rotation',) + tuple(k for k in ('title_offset_factor', 'station_offset_factor') if k in text_cfg)),
                                 ('leader', ('angle',))):
            for key in keys:
                value = structure[group_name][key]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError('structure_label.'+group_name+'.'+key+': finite number required')
        color = structure['text']['color']
        if type(color) is not int or not 1 <= color <= 255:
            raise ValueError('structure_label.text.color: ACI 1..255 required')
        if not 0 <= structure['text']['rotation'] <= 360 or not 0 <= structure['leader']['angle'] < 90:
            raise ValueError('structure_label: invalid angle')
    # G1-2D-4-FIX2: optional, independent plan annotation settings.
    plan_structure = layout['annotations'].get('plan_structure_label')
    if plan_structure is not None:
        _object(plan_structure, ('enabled', 'text', 'placement', 'layer'),
                'layout.annotations.plan_structure_label')
        if type(plan_structure['enabled']) is not bool:
            raise ValueError('plan_structure_label.enabled: boolean required')
        _object(plan_structure['text'], ('height', 'color'), 'plan_structure_label.text')
        _num(plan_structure['text']['height'], 'plan_structure_label.text.height')
        color = plan_structure['text']['color']
        if type(color) is not int or not 1 <= color <= 255:
            raise ValueError('plan_structure_label.text.color: ACI 1..255 required')
        _object(plan_structure['placement'], ('offset',), 'plan_structure_label.placement')
        offset = plan_structure['placement']['offset']
        if type(offset) not in (int, float) or not math.isfinite(offset):
            raise ValueError('plan_structure_label.placement.offset: finite number required')
        layer = plan_structure['layer']
        if (not isinstance(layer, str) or not layer.strip() or len(layer) > 255
                or any(c in layer for c in '<>/\\":;?*|=,')):
            raise ValueError('plan_structure_label.layer: invalid DXF layer name')
    # REG2-2-A: optional independent PLAN annotation group.
    plan = layout['annotations'].get('plan')
    if plan is not None:
        _object(plan, ('station', 'vip'), 'layout.annotations.plan')
        station = plan['station']
        _object(station, ('km', 'main', 'tick'), 'layout.annotations.plan.station')
        for kind in ('km', 'main'):
            item = station[kind]
            prefix = 'layout.annotations.plan.station.' + kind
            _object(item, ('enabled', 'interval', 'text', 'symbol'), prefix)
            if type(item['enabled']) is not bool:
                raise ValueError(prefix + '.enabled: boolean required')
            _num(item['interval'], prefix + '.interval')
            _object(item['text'], ('height', 'color'), prefix + '.text')
            _object(item['symbol'], ('radius', 'color'), prefix + '.symbol')
            _num(item['text']['height'], prefix + '.text.height')
            _num(item['symbol']['radius'], prefix + '.symbol.radius')
            for color_path, color in ((prefix + '.text.color', item['text']['color']),
                                      (prefix + '.symbol.color', item['symbol']['color'])):
                if color is not None and (type(color) is not int or not 1 <= color <= 255):
                    raise ValueError(color_path + ': null or ACI 1..255 required')
        tick = station['tick']
        prefix = 'layout.annotations.plan.station.tick'
        _object(tick, ('enabled', 'interval', 'length', 'color'), prefix)
        if type(tick['enabled']) is not bool:
            raise ValueError(prefix + '.enabled: boolean required')
        _num(tick['interval'], prefix + '.interval')
        _num(tick['length'], prefix + '.length')
        if tick['color'] is not None and (type(tick['color']) is not int or not 1 <= tick['color'] <= 255):
            raise ValueError(prefix + '.color: null or ACI 1..255 required')
        vip_plan = plan['vip']
        prefix = 'layout.annotations.plan.vip'
        _object(vip_plan, ('enabled', 'text', 'leader'), prefix)
        if type(vip_plan['enabled']) is not bool:
            raise ValueError(prefix + '.enabled: boolean required')
        _object(vip_plan['text'], ('height', 'color'), prefix + '.text')
        _object(vip_plan['leader'], ('stem_length', 'arm_length', 'color'), prefix + '.leader')
        _num(vip_plan['text']['height'], prefix + '.text.height')
        _num(vip_plan['leader']['stem_length'], prefix + '.leader.stem_length')
        _num(vip_plan['leader']['arm_length'], prefix + '.leader.arm_length')
        for color_path, color in ((prefix + '.text.color', vip_plan['text']['color']),
                                  (prefix + '.leader.color', vip_plan['leader']['color'])):
            if type(color) is not int or not 1 <= color <= 255:
                raise ValueError(color_path + ': ACI 1..255 required')
    for group, subgroups in LAYOUT_FIELDS.items():
        expected_groups = tuple(subgroups) + (('alignment',) if group == 'band' and 'alignment' in layout[group] else ())
        if group == 'annotations' and 'alignment' in layout['band']:
            expected_groups = tuple(k for k in expected_groups if k != 'alignment') if 'alignment' not in layout[group] else expected_groups
        if group == 'annotations' and structure is not None:
            expected_groups += ('structure_label',)
        if group == 'annotations' and plan_structure is not None:
            expected_groups += ('plan_structure_label',)
        if group == 'annotations' and plan is not None:
            expected_groups += ('plan',)
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
