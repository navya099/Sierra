"""v1.9-B.4: final_plan_vip.py symbol geometry adapted to sheet-local PLAN coordinates.
Only the VIP/grade symbol logic is reused; no structure-module dependencies.
"""
import math
from ezdxf.enums import TextEntityAlignment
from .combined_plan_profile_v1_6_core import PLAN_RECT, clip, position_at

LAYERS = ('PLAN_VIP_LINE', 'PLAN_GRADE_IN_LINE', 'PLAN_GRADE_OUT_LINE',
          'PLAN_GRADE_IN_TEXT', 'PLAN_GRADE_OUT_TEXT')

def fmt_grade(v):
    if abs(v) < 1e-8: return 'L'
    display = f'{v:.1f}'
    if display in ('0.0', '-0.0'): return '0'
    return display.rstrip('0').rstrip('.')

#REG1-FIX2-B: 기존 함수의 역할을 유지하면서 동적 평면 영역을 전달하도록 수정
def _inside(p, rect):
    return (
        rect[0] <= p[0] <= rect[2]
        and rect[1] <= p[1] <= rect[3]
    )

#REG1-FIX2-B: 기존 함수의 역할을 유지하면서 동적 평면 영역을 전달하도록 수정
def _line(msp, a, b, layer, rect):
    segment = clip(a, b, rect)
    if segment and math.dist(*segment) > 1e-8:
        msp.add_line(*segment, dxfattribs={'layer': layer})

def draw_symbol(msp, xy, tangent, grade_in, grade_out, *, stem=30., arm=10.5, text_height=3., plan_rect=PLAN_RECT):
    """Identical local geometry/labels to final_plan_vip.draw_symbol, in paper mm."""
    tx, ty = tangent
    nx, ny = -ty, tx
    def tr(x, y): return (xy[0]+tx*x+nx*y, xy[1]+ty*x+ny*y)
    pivot = (0., stem)
    # REG1-FIX2-B: 기존 함수의 역할을 유지하면서 동적 평면 영역을 전달하도록 수정
    _line(msp, tr(0, 0), tr(*pivot), 'PLAN_VIP_LINE', plan_rect)
    for grade, side in ((grade_in, 'IN'), (grade_out, 'OUT')):
        angle = math.radians(30 if grade > 1e-8 else -30 if grade < -1e-8 else 0)
        vx, vy = arm*math.cos(angle), arm*math.sin(angle)
        if side == 'IN':
            start = (-vx, stem-vy); end = pivot
            text_xy = (-vx-0.8, stem-vy+1.0)
        else:
            start = pivot; end = (vx, stem+vy)
            ux, uy = math.cos(angle), math.sin(angle)
            text_xy = (vx-0.65*ux-0.65*uy, stem+vy-0.65*uy+0.65*ux)
        # REG1-FIX2-B: 기존 함수의 역할을 유지하면서 동적 평면 영역을 전달하도록 수정
        _line(msp, tr(*start), tr(*end), f'PLAN_GRADE_{side}_LINE', plan_rect)
        text_pos = tr(*text_xy)
        # REG1-FIX2-B: 기존 함수의 역할을 유지하면서 동적 평면 영역을 전달하도록 수정
        if not _inside(text_pos, plan_rect):continue
        rotation = (math.degrees(math.atan2(ty, tx))+math.degrees(angle)) % 360
        label = msp.add_text(fmt_grade(grade), dxfattribs={
            'layer':f'PLAN_GRADE_{side}_TEXT', 'height':text_height, 'rotation':rotation})
        if side == 'OUT':
            label.set_placement(text_pos, align=TextEntityAlignment.RIGHT)
        else:
            label.dxf.insert = text_pos

def render_plan_vips(target_doc, vips, transform, *, sheet_start, sheet_end,
                     fl_points, fl_distances, station_origin=0.,
                     stem=30., arm=10.5, text_height=3., plan_rect=PLAN_RECT):
    """Assign boundary VIP to following sheet; omit end-of-route endpoint."""
    for name in LAYERS:
        if name not in target_doc.layers:
            target_doc.layers.new(name, dxfattribs={'color':1})
    msp = target_doc.modelspace()
    count = 0
    for vip in vips:
        if vip.gradient_in is None or vip.gradient_out is None: continue
        if not (sheet_start - 1e-7 <= vip.sta < sheet_end - 1e-7): continue
        distance = vip.sta - station_origin
        if distance < -1e-7 or distance > fl_distances[-1]+1e-7:
            raise ValueError(f'VIP STA {vip.sta:.3f} outside PLAN FL range')
        p = position_at(distance, fl_points, fl_distances)
        xy = transform(p)
        # REG1-FIX2-B: 기존 함수의 역할을 유지하면서 동적 평면 영역을 전달하도록 수정
        if not _inside(xy, plan_rect):continue
        # Transform a unit tangent, so symbol follows sheet rotation and not raw DXF angle.
        from bisect import bisect_right
        i = max(0, min(bisect_right(fl_distances, distance)-1, len(fl_points)-2))
        a, b = fl_points[i], fl_points[i+1]
        tangent_end = transform((p[0]+(b[0]-a[0]), p[1]+(b[1]-a[1])))
        length = math.dist(xy, tangent_end)
        if length < 1e-10: raise ValueError('Degenerate transformed FL tangent')
        tangent = ((tangent_end[0]-xy[0])/length, (tangent_end[1]-xy[1])/length)
        # REG1-FIX2-B: 기존 함수의 역할을 유지하면서 동적 평면 영역을 전달하도록 수정
        draw_symbol(msp, xy, tangent, vip.gradient_in, vip.gradient_out,
                    stem=stem, arm=arm, text_height=text_height, plan_rect=plan_rect)
        count += 1
    return count
