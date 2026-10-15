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


## v12.1 변경
- PLAN_GRADE_IN_TEXT / PLAN_GRADE_OUT_TEXT 기본 높이 4 → 3
- 구배 표시 소수점 첫째 자리 반올림, 불필요한 .0 생략
- 양수 + 생략, 음수 - 유지, 0은 L
- 위치·회전·선형·GUI 및 종평면도 출력 기능은 v12와 동일

## v12.2 변경 및 검증
- `PLAN_GRADE_OUT_TEXT`만 오른쪽 정렬(`TextEntityAlignment.RIGHT`)로 변경.
- OUT 경사선 끝점에서 선 방향 0.65 안쪽, 좌측 법선 방향 0.65에 문자 끝을 고정. 따라서 `11.5`, `-11.5`, `99.9`, `-99.9`의 마지막 자리가 끝점 안쪽에 놓이도록 설계.
- `111.5`는 예외 범위로 허용하며, 문자 시작 부분이 선 시작점 밖으로 돌출할 수 있음.
- `PLAN_GRADE_IN_TEXT`, 문자 높이 3, 1자리 소수, IN/OUT 선 길이 10.5, GUI 유지.
- 실제 원본으로 VIP 13개, IN/OUT TEXT 각 13개, ezdxf audit 오류 0건 확인.
- CAD 글꼴에 따른 실제 문자 외곽 및 이미지 71과의 시각적 일치는 사용자 CAD 확인 필요.
