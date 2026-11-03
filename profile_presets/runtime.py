"""S3-D6 Phase 2: translate schema-v2 nested layout to the stable drawing contract.

The source preset is never modified. This is an internal migration boundary,
not a reintroduction of legacy fields into the user-facing v2 JSON.
"""
from __future__ import annotations
from copy import deepcopy
from .loader import validate_preset


def to_drawing_preset(source: dict) -> dict:
    validate_preset(source)
    if source['schema_version'] == 1:
        return deepcopy(source)
    p = source['layout']
    sh, ba, pr = p['sheet'], p['band'], p['profile']
    st, sy, an = p['stations'], p['symbols'], p['annotations']
    vh, vc, vv = an['vip'], an['vertical_curve'], an['datum']
    h, bt = ba['height'], ba['text']
    cl = pr['clearance']
    band = {f'{k}_height': h[k] for k in ('alignment', 'ground', 'design', 'fill', 'cut')}
    band.update(distance_rule_offset=vh['rule']['distance_offset'], grade_rule_offset=vh['rule']['grade_offset'])
    txt = dict(data_text_height=bt['data_height'], label_text_height=bt['label_height'],
               datum_text_height=pr['datum']['text_height'], vip_text_height=vh['text_height'],
               annotation_row_height=an['row']['height'])
    annotations = dict(enabled=True, datum_label_dx=vv['label_dx'], datum_label_dy=vv['label_dy'],
        datum_break_kink_dy=vv['break_kink_dy'], alignment_station_top_inset=an['alignment']['station_top_inset'],
        vip_elevation_text_height=vh['elevation_text_height'], vip_caption_text_height=vh['caption_text_height'],
        vip_caption_gap_factor=vh['caption_gap_factor'], curve_ordinate_offset=vc['ordinate_offset'],
        curve_endpoint_text_offset=vc['endpoint_text_offset'], curve_endpoint_line_height=vc['endpoint_line_height'],
        curve_text_height=vc['text_height'], vip_distance_text_offset=vh['distance_text_offset'],
        vip_distance_text_height=vh['distance_text_height'], vip_arrow_half_height=vh['arrow_half_height'],
        vip_arrow_length=vh['arrow_length'], grade_text_height=an['grade']['text_height'],
        distance_text_height=an['distance']['text_height'])
    lower = sh['drawing_limits']['plot_lower_y']
    upper = sh['drawing_limits']['plot_upper_y']
    result = deepcopy(source)
    result['schema_version'] = 1  # internal drawing contract only
    result['layout'] = {
        'sheet': dict(origin_x=sh['origin']['x'], origin_y=sh['origin']['y'],
                      start_margin=sh['margin']['start'], end_margin=sh['margin']['end'],
                      label_column_width=ba['column']['label_width']),
        'profile': dict(plot_lower_y=lower, plot_upper_y=upper,
                        datum_step_m=pr['datum']['step_m'], datum_safety_margin_m=pr['datum']['safety_margin_m']),
        'band': band,
        'text': txt,
        'symbols': dict(vip_circle_radius=sy['vip']['circle_radius'],
                        datum_break_width=sy['datum']['break_width'], datum_break_height=sy['datum']['break_height']),
        'stations': dict(station_interval=st['grid']['sub_interval'], major_interval=st['grid']['main_interval'],
                         band_interval=st['text']['band_interval'],
                         alignment_station_interval=st['text']['alignment_station_interval']),
        'placement': dict(enabled=False, band_to_profile_gap=cl['band_to_profile_gap'],
                          reserved_structure_depth=cl['reserved_structure_depth'],
                          structure_clearance=cl['structure_clearance'],
                          profile_plot_height=pr['plot']['height'], datum_label_offset=12.0),
        'expansion': dict(enabled=False, band_height_factor=1.0,
                          label_column_width=ba['column']['label_width'], text_height_factor=1.0,
                          profile_plot_height=pr['plot']['height'], use_placement_clearance=cl['use_placement_clearance']),
        'absolute_dimensions': {
            'enabled': True, 'sheet': {'label_column_width': ba['column']['label_width']},
            'band': deepcopy(band), 'text': deepcopy(txt),
            'profile': dict(plot_lower_y=lower, plot_height=pr['plot']['height'],
                            band_to_profile_gap=cl['band_to_profile_gap'],
                            reserved_structure_depth=cl['reserved_structure_depth'],
                            structure_clearance=cl['structure_clearance'],
                            use_placement_clearance=cl['use_placement_clearance'])},
        'annotations': annotations,
    }
    validate_preset(result)
    return result
