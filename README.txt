종평면도 v1.4.2 — 패키지 구조 정리 (v1.4 원본 기준)

압축 파일의 내용을 D:\git\Sierra\ 아래에 그대로 풀어주세요.
기존 Sierra 최상위 profile_drawing.py, profile_split.py 등은 이동/수정하지 않습니다.
신규 엔진은 combined_plan_profile/profile_engine 안에 격리했습니다.

테스트 실행 (D:\git\Sierra):
python combined_plan_profile_v1_4.py --plan "test_data/테스트용_FL_가상선형.dxf" --profile "test_data/테스트용_가상종단.dxf" --sheet-length 200 --horizontal-scale 1000 --vertical-scale 400

실제 입력은 --plan/--profile 경로를 실제 파일로 바꾸세요.
출력 기본 경로: combined_plan_profile/출력/

변경 범위: import 경로와 패키지 구성만 변경. 기존 v1.4 PLAN/PROFILE 작도 알고리즘은 그대로 유지.
