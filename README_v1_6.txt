v1.6 좌측 시점 정렬 시험판
기존 v1.4.2/v1.5 파일은 변경하지 않음.
PLAN 시트 시작 측점 X=70mm, Y=430mm; PROFILE X=70mm.
평면선형 시트 시작~끝 chord 방향 자동 회전 및 클리핑 유지.
실행: python combined_plan_profile_v1_6.py --plan "C:/temp/본선평면선형.dxf" --profile "C:/temp/converted_dxf.dxf" --sheet-length 200 --output-dir "combined_plan_profile/출력_v1_6"
주의: 기존 v1.5와 동일한 출력 폴더를 지정하면 같은 파일명을 덮어쓸 수 있으므로 출력 폴더를 분리하세요.
