Sierra 종평면도 v1.8-B.1 정리본 (IP문자 + IP제원표 연결 확인)

[중요] 기존 D:\git\Sierra\combined_plan_profile 폴더와 파일을 혼합하여 덮어쓰지 마세요.
이 ZIP을 D:\git\Sierra\종평면도_v1_8B1_정리본 같은 새 폴더에 통째로 압축 해제하고
그 새 폴더에서 실행해야 이전 모듈 혼재를 방지할 수 있습니다.

의존성: Python 3.11 이상, ezdxf (pip install ezdxf)

실행 예:
python combined_plan_profile_v1_8a.py --plan "C:/temp/본선평면선형.dxf" --profile "C:/temp/converted_dxf.dxf" --sheet-length 700 --horizontal-scale 1000 --vertical-scale 400 --start-sta 2000 --end-sta 3700 --output-dir "출력_v1_8b1"

[IP문자/제원표] 로그가 매 시트 표시되면 신규 함수가 실제 호출된 것입니다.
IP가 도각 밖이면 자동 제외되며 위치를 강제 보정하지 않습니다.
2000~3700m 구간에서는 원본 IP가 멀어 문자/블록 0개 출력도 정상일 수 있습니다.

정리: 과거 combined_plan_profile_v1_3~v1_7 실행기/구버전 README, __pycache__,
현재 종평면도 출력에 직접 필요 없는 공사비/GUI/구조물 엔진 파일 제거.
기존 안정 버전의 FL/IP라인/측점 처리 및 시간 로그 유지.
