# 단곡선 BC/EC 도식 검증 (v11.6 기반)

기존 v11.6 소스 변경 없이, 테스트용 평면 DXF만 별도 생성했습니다.

- BC=1km234.56, EC=2km345.67 (가상 측점)
- 우향 곡선, 오프셋 +6mm, 직선 적색 ACI 1 / 곡선 흰색 ACI 7
- BC/EC 문자 흰색 ACI 7, 높이 2.4mm, 도식에서 아래로 3mm
- 단곡선 BC/EC에서 수직 전환선은 흰색으로 표현됩니다.
- R/IA/TL은 CL=1111.11m와 기하학적으로 일치하도록 시험용으로 계산했습니다. 실제 노선 제원이 아닙니다.

검증 파일: test_simplecurve_BC_EC.dxf
입력 파일: synthetic_simplecurve_BC1234_EC2345.dxf

실행 예:
`python profile_drawing.py converted_dxf.dxf --alignment-dxf synthetic_simplecurve_BC1234_EC2345.dxf --output test_simplecurve_BC_EC.dxf`

**주의:** 시험용 평면 DXF와 converted_dxf.dxf는 동일 노선이 아닙니다. 문자 및 도식 검증 용도로만 사용하세요.
