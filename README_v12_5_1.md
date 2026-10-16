# v12.5.1 구조물 관리 GUI

- `main_gui.py` → `구조물 관리` 탭
- 자동 판정 기준: 터널 절토고 40m / 최소 100m, 교량 성토고 15m / 최소 100m (GUI에서 변경 가능)
- `자동 후보 생성` 시 현재 GUI에 설정된 **VIP 종곡선 길이**를 실시간으로 `VerticalAlignment`에 반영하여 구조물 후보를 재계산합니다.
- 후보를 선택하고 `수정` 또는 더블클릭: 종류/명칭/시작/종료 측점 변경. `추가`, `삭제`도 지원합니다.
- 수정한 항목의 출처는 `MANUAL`로 변경됩니다. CSV 저장 및 불러오기 지원.
- 자동 후보 재생성은 현재 편집 목록을 교체하므로 확인 대화상자를 표시합니다. 편집 내용은 먼저 CSV로 저장하세요.
- 구조물 도면 출력은 아직 미구현이며 다음 단계에서 연결합니다. 기존 v12.4.0 종단 DXF 출력과 v12.3.10 종곡선 출력은 변경하지 않았습니다.
- 수동 수정한 항목의 최대고/최대고 측점은 자동으로 다시 계산하지 않으며 이전 후보 메타데이터를 유지합니다. 최종 측점이 바뀐 경우 재계산은 추후 개선 항목입니다.
- 종곡선 설정을 변경한 뒤 `자동 후보 생성`을 다시 눌러야 후보 목록이 갱신됩니다. 자동으로 수동 수정 결과를 덮어쓰지 않습니다.

## 실행
`python main_gui.py`

## 검증
`python -m unittest test_vertical_curve test_structure_engine`
14 tests pass. Python syntax compilation pass. GUI interaction requires Windows manual check.
