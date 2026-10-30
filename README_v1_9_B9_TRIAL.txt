v1.9-B.9 평면 구조물 통합 시험판 (2026-10-30)

기반: 사용자 승인 v1.9-B.8. 종단 엔진/기존 시트 코어 유지.
추가: plan_structure_renderer_b9.py 및 기존 평면 구조물 작도 엔진 7개.
기능: 교량 슬래브/거더, 교각/기초, 교대(템플릿 지정 시), 터널 본체,
      기본/사용자 지정 갱문, 평면 구조물 레이블.

실행: 기존 B.8과 동일하게 python -m combined_plan_profile.combined_plan_profile_v1_8a ...
--structures-csv 및 --structure-settings-json 옵션 그대로 사용.

JSON의 기존 키에 'plan' 키 추가 가능:
"plan": {
  "bridge_nominal_span": 30.0,
  "bridge_abutment_plan_dxf": "C:/path/to/교대일반도.dxf",
  "labels_enabled": true,
  "pier": {"column_diameter":3.0,"coping_width":6.0,"coping_length":6.0,
           "foundation_width":9.0,"foundation_length":9.0},
  "label": {"offset":15.0,"height":3.0,"layer":"STRUCTURE_LABEL_PLAN","color":1}
}

기본 동작: 교대 DXF 경로 미지정이면 교대만 생략하며 로그로 알림.
전체 FL을 기반으로 구조물 형상을 1회 생성하고 각 시트의 Matchline 폴리곤으로 절단.
교각 CIRCLE은 72각형 폴리라인으로 근사; 폐합 폴리라인은 폴리곤 클리핑.
문자는 삽입점 기준 포함 여부만 판단(글자 외곽 전체 클리핑 미지원).
기본 갱문이 전체 FL 범위를 벗어나면 해당 기본 갱문 작도는 생략하고 로그 출력.

검증: Python import/compileall, 합성 직선 FL(1000m), 교량+터널 2개
      도형 생성 및 시트 클리핑 함수 실행 성공.
미검증: 실제 사용자 PLAN/PROFILE/DXF 도곽으로 최종 시트 렌더링,
        곡선부 Matchline/교대 DXF/사용자 갱문, AutoCAD 육안 확인.

주의: B.8 원본을 덮어쓰지 말고 별도 폴더에 압축 해제 후 시험.
