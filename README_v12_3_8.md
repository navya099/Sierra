# v12.3.8 종거 계산 기준 수정

- v12.3.7 승인된 배치/레이어/수직선 길이 유지
- PVC~VIP: 진입 접선 기준, VIP~PVT: 진출 접선 기준
- 부호 있는 종거값 유지. PVC/PVT=0, VIP에서 절댓값 최대
- 계산식: Δg(‰)/1000 × min(x, L-x)² / (2L)
- 종곡선 표고/구배 계산과 평면도 출력 변경 없음
- 테스트: `python -m unittest test_vertical_curve.py`
