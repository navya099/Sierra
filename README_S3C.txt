Sierra v2.0-S3-C GUI 연결 시험판 (2026-11-02)

적용 전제: S3-B 적용 완료한 feature/profile-multiscale-v2 브랜치.

1. ZIP의 Sierra_v2.0_S3C.patch를 D:\git\Sierra 에 복사
2. git apply --check Sierra_v2.0_S3C.patch
3. git apply Sierra_v2.0_S3C.patch
4. python -m unittest -v test_s3b_dxf_modes.py test_s3a_transform.py test_profile_transform.py
5. GUI 실행 후 도면 출력 옵션에서 CAD/보고서, 프리셋, H/V, 수직 과장 체크

주의:
- 패치는 main_gui.py만 수정하며 기존 S3-B profile_drawing.py와 profile_transform.py가 필요합니다.
- 기본값은 기존 출력 결과 보존을 위해 보고서 모드 H1000/V400, 과장 ON입니다.
- CAD 모드의 X=1:1 좌표 변환은 S3-B 엔진을 사용합니다.
- CAD 도곽, 문자, 밴드, 구조물 등의 배치/단위 정합성은 아직 S3-D 대상입니다.
- 최종 평면도는 별도 엔진이며 이번 옵션이 영향을 주지 않습니다.
- 실제 GUI/AutoCAD 시각 검증 전에는 안정판으로 확정하지 마세요.
- 기존 main_gui.py가 변경되어 git apply --check 실패하면 덮어쓰지 말고 충돌 내용을 공유하세요.
