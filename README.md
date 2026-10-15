# v12.3.2 종곡선 종평면도 출력 시험판

v12.3.1 기반. 기존 GUI 및 최종 평면도는 그대로 유지합니다.

- 종곡선 설계 탭에서 VIP별 L 입력 후 **종평면도 DXF에 종곡선 적용** 체크 (기본 OFF).
- 도면 출력에서 종평면도 선택 시 `final_result.dxf`의 `PLAN_PROFILE`을 포물선 근사 폴리라인으로 출력합니다.
- 계획고/성토/절토 밴드 및 자동 Datum 계산도 종곡선 설계고를 반영합니다.
- 곡선 내부 최대 2m 간격, PVC/PVT 및 최고·최저점 정확한 정점 포함.
- VIP 주석/구배 거리 도식은 기존 접선 기준 유지 (추후 PVC/PVT 주석 별도 개발).
- 최종 평면도 `final_plan_result.dxf`는 기존 v12.2 방식 그대로입니다.
- 체크 OFF면 기존 v12.2 종평면도 출력 경로를 사용합니다.
- 길이 설정은 아직 메모리에서만 유지됩니다.

## 테스트
`python -m unittest -q test_vertical_curve`
`python test_vertical_curve_drawing.py`
