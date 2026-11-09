# Sierra 재현용 테스트 자산

이 파일들은 저장소 루트에서 실행하는 회귀테스트용입니다.

- cad/도각.dxf: A1 기준 도각
- cad/교대일반도.dxf: 교대 평면 템플릿
- cad/converted_dxf.dxf: 종단 입력
- cad/본선평면선형.dxf: 평면 입력
- config/: 도각 속성 및 구조물 상세 설정
- data/structure_segments.csv: 구조물 입력

주의: config/structure_settings_B8_example.json의 교대 경로는 저장소 루트 기준 상대경로입니다.
실행 작업 디렉터리가 저장소 루트가 아니면 현재 엔진에서는 경로를 못 찾을 수 있습니다.
GUI에서 임시 JSON을 생성하는 경우에도 교대 경로가 올바른지 확인하세요.

실행 예 (저장소 루트에서 PowerShell):
python -m combined_plan_profile.combined_plan_profile_v1_8a --plan assets/test/cad/본선평면선형.dxf --profile assets/test/cad/converted_dxf.dxf --template assets/test/cad/도각.dxf --structures-csv assets/test/data/structure_segments.csv --structure-settings-json assets/test/config/structure_settings_B8_example.json --titleblock-config assets/test/config/titleblock_config.json --output-dir test_output --sheet-length 700 --horizontal-scale 1000 --vertical-scale 400 --start-sta 0 --end-sta 1000

FIX2 이전 단계의 테스트 데이터이며, 자동 실행 결과는 사용자 Windows 환경에서 검증해야 합니다.
