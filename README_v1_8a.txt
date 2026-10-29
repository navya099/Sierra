v1.8-A IP교점선 추가 시험판
- v1.7.2 안정 파일 보존
- IP교점선만 신규 모듈에서 처리; IP문자/IP_Block_*는 다음 단계
- IP라인 꼭짓점에 가장 가까운 IP교점선의 시트 소속 측점을 판별
- FL 투영 측점으로 범위 필터, A1 PLAN 영역으로 선분 클리핑
- 실행: python combined_plan_profile_v1_8a.py --plan "C:/temp/본선평면선형.dxf" --profile "C:/temp/converted_dxf.dxf" --sheet-length 700 --horizontal-scale 1000 --vertical-scale 400 --start-sta 2000 --end-sta 3700 --output-dir "combined_plan_profile/출력_v1_8a"
- 주의: 원본 IP라인의 꼭짓점은 IP 교점이어야 함; IP 선형이 없으면 중점 투영으로 대체
