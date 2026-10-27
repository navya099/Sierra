"""종평면도 v1.0: 외부 A1 도곽 + 독립 사각형 영역 검증.

기존 final_plan / final_result DXF 및 생성 코드를 읽거나 수정하지 않는다.
실제 평면/종단 데이터 작성 및 클리핑은 후속 버전에서 구현한다.
"""
from pathlib import Path
import argparse
import ezdxf

# mm, template modelspace coordinates. Rectangles are test-only guides.
DRAWING_AREAS = {
    'PLAN': (35.0, 330.0, 811.0, 530.0),
    'PROFILE': (35.0, 70.0, 811.0, 315.0),
}

def build(template: Path, output: Path, show_guides: bool = True) -> Path:
    doc = ezdxf.readfile(str(template))
    msp = doc.modelspace()
    doc.header['$INSUNITS'] = 4  # millimeters
    for layer, color in [('ZPP_PLAN_AREA', 3), ('ZPP_PROFILE_AREA', 5), ('ZPP_GUIDE_LABEL', 7)]:
        if layer not in doc.layers:
            doc.layers.new(layer, dxfattribs={'color': color})
    if show_guides:
        for name, (xmin, ymin, xmax, ymax) in DRAWING_AREAS.items():
            layer = 'ZPP_PLAN_AREA' if name == 'PLAN' else 'ZPP_PROFILE_AREA'
            msp.add_lwpolyline([(xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax)], close=True, dxfattribs={'layer':layer})
            msp.add_text(f'{name}_RECT  ({xmin:g},{ymin:g}) - ({xmax:g},{ymax:g})', dxfattribs={'height':5, 'insert':(xmin+6,ymax-11), 'layer':'ZPP_GUIDE_LABEL'})
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output))
    return output

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--template', type=Path, default=Path(__file__).with_name('도각.dxf'))
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('종평면도(1).dxf'))
    parser.add_argument('--no-guides', action='store_true')
    args=parser.parse_args()
    print(build(args.template,args.output,not args.no_guides))
