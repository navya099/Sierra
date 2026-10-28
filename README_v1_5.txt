v1.5 실제 노선 DXF 연결 시험판

기존 v1.4.2 패키지 및 Sierra 루트 안정 모듈은 수정하지 않았습니다.
새 진입점 combined_plan_profile_v1_5.py 만 추가되었습니다.

Windows 실행:
python combined_plan_profile_v1_5.py --plan "C:/경로/평면선형.dxf" --profile "C:/경로/종단선형.dxf" --sheet-length 200 --dry-run
python combined_plan_profile_v1_5.py --plan "C:/경로/평면선형.dxf" --profile "C:/경로/종단선형.dxf" --sheet-length 200

주의:
- 평면 입력은 FL 단일 열린 LWPOLYLINE(직선 정점), 종단 입력은 기존 profile_engine에서 인식하는 PLAN_PROFILE 및 지반 데이터여야 합니다.
- FL 누적거리를 측점으로 사용합니다. 원본 선형의 Civil3D 측점과 차이가 있는 경우 측점 대응 검증이 필요합니다.
- 기존 Sierra GUI 옵션 전달, 구조물 및 종곡선 설정 전달은 미구현입니다.
- 본 버전은 실제 파일로 시험할 수 있는 CLI 및 측점 범위 사전 검증 단계입니다.
