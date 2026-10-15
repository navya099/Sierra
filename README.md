# 종평면도 + 최종 평면도 통합 출력 v12

- 기준: 승인된 평면선형 밴드 v11.6, Final Plan VIP v1.1
- GUI: `main_gui.py` -> 도면 출력 (DXF) -> 종평면도 / 최종 평면도 선택
- 원본: 종단 설계 DXF와 평면선형 DXF는 읽기 전용으로 사용
- 출력 폴더: `final_result.dxf` / `final_plan_result.dxf`
- 최종 평면도는 원본 FL 측점-좌표/접선 보간을 사용하며, GUI에서 계산된 VIP 목록을 직접 전달
- 양쪽 출력은 각각 실패를 처리하며 성공한 출력은 유지
- 기존 파일은 덮어쓰기 전에 사용자에게 확인
- 입력 원본과 출력 대상의 경로 충돌 방지
- 기존 종평면도 출력 옵션(축척/Datum/평면선형 밴드) 유지

## 실행

`pip install ezdxf` 후 `python main_gui.py`

## 실물 DXF 검증

`test_final_result.dxf`, `test_final_plan_result.dxf` 두 파일 모두 ezdxf audit 오류 0.
VIP 13개 일치.

## 주의

Tkinter GUI 버튼 클릭 동작은 이 실행 환경에서 직접 시각적으로 검증하지 못했습니다.
두 DXF 생성 함수의 실제 출력 및 Python 문법 검사는 통과했습니다.
평면선형 DXF를 처음 지정하면 최종 평면도 옵션을 자동으로 켭니다.
