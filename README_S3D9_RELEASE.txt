Sierra v2.0 — S3-D9 Custom Preset Loader RELEASE Candidate

검증 결과: python -m pytest -q → 131 passed, 41 subtests passed (Python 3.13, Linux).
사용자 Windows GUI 검증: custom_preset.json CAD H600/V100 정상 출력 확인.
기존 내장 CAD H1000/V400, H5000/V1000 RELEASE Windows GUI 검증 완료.

변경 내역:
- 기존 S3-D1/D2/D6 테스트는 test_fixtures에 고정된 v1 기준 프리셋으로 검증하도록 분리.
- v2 DXF 회귀는 같은 v2 설정을 내부 v1 drawing contract로 변환한 결과와 비교.
- S3-D8.3 사용자 조정 문자 위치와 구형 factor 기반 테스트 분리.
- S3-D9 커스텀 프리셋 검증 5개 추가: 외부 파일, 모드/축척 불일치, 상태/치수 오류, BOM/복사 격리, 내장 RELEASE 보존.
- custom_preset.json 사용자 제공 H600/V100 설정값 보존, 구버전 초안 notes만 현재 설명으로 갱신.

주의: Windows GUI 테스트는 사용자가 이전 S3-D9 시험판에서 성공을 확인했으며,
본 배포 후보 ZIP 자체의 Windows GUI 재실행은 아직 수행하지 않음.
