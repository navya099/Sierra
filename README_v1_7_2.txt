v1.7.2 마지막 시트 1km/200m 심볼 및 문자 범위 필터 수정
- v1.7.1의 보조측점 LINE 필터 유지
- km심볼, 200심볼 CIRCLE 및 km문자, 200문자 TEXT/MTEXT 원본 위치를 FL에 투영
- 해당 시트 시작~종료 측점 밖 객체 제외 (시트 마지막 3700 이후 제거)
- PLAN 사각형 클리핑은 기존대로 유지
- 기존 v1.6.2 및 v1.7.1 코드/동작은 원본 보존
- 실행: python combined_plan_profile_v1_7.py --plan ... --profile ... --sheet-length 700 --start-sta 2000 --end-sta 3700 --output-dir combined_plan_profile/출력_v1_7_2
