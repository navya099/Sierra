# v12.5.0 구조물 자동 판정 엔진 (시험판)

기반: 승인된 v12.4.0 전체 프로젝트. 기존 GUI, 종곡선, 분할 DXF 코드는 변경하지 않음.

## 판정 규칙
- 터널: 연속 절토 구간 길이 >= 100m, 최대 절토고 >= 40m
- 교량: 연속 성토 구간 길이 >= 100m, 최대 성토고 >= 15m
- 네 기준은 CLI에서 수정 가능. 구간은 절토/성토 전환점을 보간하여 결정.
- 종곡선 적용 시 `--curves-json` 으로 기존 VIP별 곡선 길이 지정 가능.
- 기본 실행은 종곡선 미적용(길이 사전 비어 있음). GUI에서 설정한 종곡선 길이는 아직 자동 연동되지 않음.
- 자동 판정은 예비 후보만 생성. 최종 구조물 설계 기준이 아님.

## 실행 (Windows Python 3.11)
```
python structure_engine.py C:\TEMP\converted_dxf.dxf C:\TEMP\structure_candidates.csv
python structure_engine.py C:\TEMP\converted_dxf.dxf C:\TEMP\structure_candidates.csv --tunnel-cut 40 --tunnel-min 100 --bridge-fill 15 --bridge-min 100
python -m unittest test_structure_engine test_vertical_curve
```

`--curves-json` JSON 파일 예시: `{"6": 300}` (VIP 인덱스는 0부터 시작; GUI 인덱스와 일치 여부 확인 필요).

CSV 출력 컬럼: kind, name, start_sta, end_sta, length, max_height, peak_sta, source.
수동 수정된 CSV는 `load_manual_csv`로 별도 불러올 수 있으며 자동 재계산 결과와 독립적으로 보존 가능.
**아직 GUI 편집/저장 기능과 평면·종단 DXF 구조물 표기는 구현하지 않음.**

## 주의
원본 DXF는 읽기 전용이며 출력 CSV만 생성. 지반선은 구간별 선형 보간, 계획선은 종곡선 포함 계산. 길이와 표고는 실제 m 단위.
