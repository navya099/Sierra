"""D5 개략/세부 선택 및 통합 진입점.

공종별 ROUGH/DETAIL/NONE 배타 선택. 원본 XLSX와 총사업비 출력 계약 유지.
"""
from .cost_integrated import GROUPS, SourceLine, read_cost_workbook, integrate_costs, export_integrated_cost

MODES = ('ROUGH', 'DETAIL', 'NONE')

def decide_costs(rough_file=None, detail_file=None, selected=None):
    """두 독립 엔진의 기존 산출 XLSX를 읽어 D5 통합 결과 반환.

    미선택 공종은 미산정이며, 세부 누락분을 개략으로 자동 보충하지 않는다.
    """
    selected = dict(selected or {})
    unknown = set(selected) - set(GROUPS)
    if unknown:
        raise ValueError(f'지원하지 않는 공종: {", ".join(sorted(unknown))}')
    for group, mode in selected.items():
        if mode not in MODES:
            raise ValueError(f'{group}: 잘못된 산정방식 {mode}')
    rough = read_cost_workbook(rough_file, 'ROUGH') if rough_file else []
    detail = read_cost_workbook(detail_file, 'DETAIL') if detail_file else []
    return integrate_costs(rough, detail, selected)
