Sierra v2.0 S3-D8.2 — 구조물 종단 레이블 프리셋 분리 (Windows GUI 시험판)

기준: S3-D7.5 GUI 검증 버전, h5000_v1000(5).json

- 구조물 주석 UI에는 측점 표기 방식/사용자 접두어/교량 형식만 남김.
- layout.annotations.structure_label.text / leader 항목 추가.
- structure_label.py: ProfileLabelStyle 신규 추가, 종단 레이블에만 적용.
- 평면 구조물 레이블은 기존 LabelSettings 및 PlanLabelSettings 사용.
- 새 항목 없는 schema v2 프리셋: 종전 3/1/3/30/30도 기본값 사용.
- 기존 schema v1 프리셋은 종전 방식 유지.
- 프리셋 H5000/V1000는 사용자가 확정한 (5) 값을 유지하면서 구조물 설정 추가.

테스트: 신규 6/6 PASS, 전체 116개 중 115 PASS / 1 FAIL.
기존 실패: test_s3d6_runtime.test_legacy_no_mutation (기본 프리셋 schema v2인데 v1을 가정하는 테스트).

Windows 확인: 구조물 명칭/측점 접두어/교량 형식 편집, 종단 레이블 크기/인출선 변경,
평면 레이블 보존, 기존 S3-D7.5 평면선형 밴드 출력 보존.
