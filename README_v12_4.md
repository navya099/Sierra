# v12.4.0 독립 종단면도 분할

- GUI 도면 출력 옵션에서 `독립 DXF 분할` 체크, 분할 길이(m) 입력.
- 출력: `종단면도(1).dxf`, `종단면도(2).dxf` ...
- 원본 종단선형/종곡선 계산은 전체 범위에서 수행하고 각 도면에 표시되는 범위만 절단.
- Datum은 각 구간 내 지반고/계획고를 기준으로 다시 계산.
- 평면도 출력은 기존 `final_plan_result.dxf` 유지.
- 분할 미선택 시 기존 `final_result.dxf` 유지.
- CLI 사용: `from profile_split import export_split_profiles; export_split_profiles(source, folder, 700, options, lengths)`
- 파일 합치기 기능은 구현하지 않음.
