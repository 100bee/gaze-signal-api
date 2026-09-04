# 실기기 검증 기록

## 2026-09-04 현재 결과

검증 환경은 Apple M5, macOS 26.6.2 arm64, Python 3.12다.

| 항목 | 결과 | 근거/남은 일 |
|---|---|---|
| MediaPipe 패키지·모델 | 실기 성공 | Face Landmarker가 Metal 2.1과 TFLite XNNPACK delegate로 초기화됐고 실제 640×480 카메라 프레임 58개 모두에서 분석기 가용·얼굴 검출에 성공했다. 모델 SHA-256도 다운로드 스크립트와 일치한다. |
| 실제 macOS 카메라 | 성공 | Terminal 카메라 권한 허용 후 AVFoundation 카메라 0번에서 640×480 프레임을 획득했다. 원본 프레임은 저장되지 않았다. |
| 얼굴 랜드마크 E2E | 성공 | 10초 중앙 응시 smoke test에서 `face_analysis_available_ratio=1.0`, `face_present_ratio=1.0`을 확인했다. 다른 조명·안경·거리 조건은 미검증이다. |
| head-pose 수학 부호 | 합성 성공/실기 일부 | 알려진 yaw ±20°, pitch ±15°, roll 10°를 합성 복원했다. 실제 중앙 응시 median은 yaw −11.931°, pitch 5.982°, roll 2.355°로 중립 offset 보정 필요성을 확인했다. 방향별 부호 검증은 남아 있다. |
| gaze 좌우 | 합성 성공/실기 일부 | 실제 중앙 응시에서 feature median x=0.506, y=0.427, zone은 center 54/58, away 1/58, up 3/58이었다. 이는 중앙 조건 smoke 결과이며 정확도 수치가 아니다. |
| 5점/9점 UI | 코드 검토 완료/실기 미완료 | 표적별 안정화, 유효 샘플 수, 6초 timeout, 전체화면 이탈 취소, 계수 별도 삭제를 구현했다. 실제 두 패턴의 완료율·소요 시간은 측정해야 한다. |
| YOLO 설치·추론 | 부분 성공 | Ultralytics 8.4.115/Torch 2.14.0과 YOLO11n 가중치를 설치하고 640×640 빈 프레임 추론이 오류 없이 `phone_visible=false`를 반환했다. 실물 휴대폰 precision/false positive는 미검증이다. |
| SQLite 동시성 | 자동 성공 | WAL 모드에서 4 worker, 8 batch, 80 event 동시 쓰기를 검사한다. 장시간 soak test는 남아 있다. |

첫 실행은 58 frame/10초였고 frame-local latency는 p50 7.845ms, p95 9.074ms였다. 모델·Matplotlib 최초 초기화가 측정 구간에 포함되어 이 frame 수를 정상 FPS로 해석하지 않는다. 이후 smoke script는 별도 warm-up 후 `effective_fps`와 최대 latency를 출력하도록 수정했다.

## 카메라 권한을 켠 뒤 실행할 명령

카메라 앞 사람의 동의를 확인하고, 명령을 실행하는 앱의 macOS 카메라 권한을 켠다. 원본 프레임은 저장되지 않는다.

```bash
.venv/bin/python scripts/hardware_smoke.py --consent --seconds 10
.venv/bin/python scripts/hardware_smoke.py --consent --guided-pose
.venv/bin/python scripts/hardware_smoke.py --consent --seconds 10 --yolo
```

그 다음 로컬 콘솔에서 5점과 9점을 각각 세 번 완료하고 다음을 기록한다.

- 패턴별 완료/timeout 횟수, 소요 시간, 학습 RMSE
- 캘리브레이션에 쓰지 않은 표적의 held-out zone confusion matrix
- 고개 좌/우/상/하의 median yaw/pitch와 기대 부호
- 안경, 역광, 저조도 조건의 face-present/unknown 비율
- 휴대폰 없음/정면/부분 가림 조건의 검출과 false positive
- 세션 중지·즉시 재시작, 카메라 점유 앱 종료 후 재연결, 서버 종료 후 DB 상태

권한을 변경하기 위해 `tccutil reset Camera`를 자동 실행하지 않는다. 기존 앱 권한을 함께 초기화할 수 있으므로 사용자가 macOS 설정에서 명시적으로 변경한다.
