# 평가 계획

현재 저장소의 자동 테스트는 알고리즘·API 동작을 검증하지만 실제 사람/카메라 정확도를 증명하지 않는다. 아래 프로토콜을 대상 장치에서 실행하고 재현 조건을 함께 공개한 경우에만 성능 수치를 사용한다.

## 1. Gaze zone 정확도

### 데이터 수집

1. 명시적으로 동의한 참여자에게 5점 또는 9점 캘리브레이션을 수행한다.
2. fit에 쓰지 않은 순서 무작위 표적을 zone마다 최소 20회 제시한다.
3. 표적 표시 후 500 ms 적응 구간은 제외하고 1–2초 파생 이벤트만 기록한다.
4. 원본 얼굴 영상은 저장하지 않는다. ground truth zone, predicted zone, confidence, 조명/안경/머리 조건만 CSV로 저장한다.
5. 동일 사람의 calibration/test가 섞이지 않도록 세션별로 분리한다.

### 보고 지표

- 전체 zone accuracy = 정답 frame / 전체 평가 frame
- known-only accuracy = unknown을 제외한 frame에서 accuracy
- unknown ratio = predicted `unknown` / 전체
- 7×7 confusion matrix(center/left/right/up/down/away/unknown)
- zone별 precision/recall(표본 수와 함께)
- calibration RMSE와 held-out target error

전체 accuracy만 높이기 위해 unknown을 숨기지 않는다. unknown 비율과 confidence calibration을 함께 공개한다.

`python scripts/evaluate_zones.py results.csv`가 기본 confusion matrix를 JSON으로 출력한다. CSV는 `true_zone,predicted_zone` 열이 필수다.

## 2. 조건별 평가

다음 strata를 각각 보고한다.

- 안경: 없음 / 투명 / 반사 심함
- 조명: 정면 양호 / 역광 / 저조도
- 카메라 위치: 화면 상단 중앙 / 좌우 편심 / 낮은 각도
- head pose: 정면, yaw ±15°/±30°, pitch ±15°/±25°
- 얼굴 크기와 이동, 모션 블러

표본이 적으면 평균값을 일반화하지 말고 실패 사례로 서술한다. 얼굴 영상이나 개인 식별자는 저장소에 커밋하지 않는다.

## 3. 시간축 상태 평가

합성 timestamp 신호로 debounce 정확성을 자동 테스트하고, 실기기에서는 다음 시나리오를 반복한다.

- 200 ms away spike는 상태 전환이 없어야 한다.
- 설정된 1초 이상 away가 지속되면 허용 오차 안에서 한 번 전환되어야 한다.
- 얼굴 가림과 gaze away는 서로 다른 상태로 기록되어야 한다.
- 모델 미가용은 `face_missing`이 아니라 `unknown`이어야 한다.

전환 지연 분포와 false transition/minute를 보고한다.

## 4. 성능

대상: 최소 한 대의 Apple Silicon MacBook과 가능하면 Intel Mac.

| 지표 | 방법 | 목표 |
|---|---|---|
| effective FPS | 저장 event count / session duration | 기본 pipeline ≥15 FPS |
| processing latency | event의 `processing_latency_ms` p50/p95 | p95 ≤300 ms |
| end-to-end WS latency | client receive monotonic time - frame timestamp 보정 | p95 ≤300 ms |
| CPU/RSS | Activity Monitor 또는 `psutil` 별도 측정 | 수치 보고, 목표는 기기별 설정 |
| dropped frames | LatestFrameBuffer counter | 지속 증가 여부와 모델 설정 비교 |

30초 warm-up 후 5분 측정하고 세 번 반복한다. MediaPipe only와 MediaPipe+YOLO를 같은 해상도/FPS에서 비교하며, YOLO N=5/10/30을 구분한다. `python scripts/benchmark_events.py events.json`은 export한 event 배열에서 FPS와 latency p50/p95를 계산한다.

## 5. 실패/복구

- 카메라 권한 거부: 503, 내부 경로 없음
- 실행 중 카메라 분리: 제한 재시도 후 `failed`
- Face Landmarker asset 삭제/손상: session 지속, available=false/unknown
- YOLO asset 삭제/손상: phone detector만 중단
- 느린 분석 mock: queue 크기가 1을 넘지 않고 최신 frame 우선
- 서버 종료: camera/model/DB release, running session 종료 상태

## 6. 자동 테스트와 실제 검증의 경계

자동 테스트 통과는 affine 수학, enum 분류, 시간 적분, CRUD와 오류 계약을 보장한다. 랜드마크 정확도, gaze zone accuracy, 안경/피부톤/조명별 공정성, CPU 15 FPS는 실제 평가 없이는 주장할 수 없다.

검증 결과표에는 장치 모델, OS, Python/모델 버전, 화면/카메라 해상도, 표본 수, calibration 방법, 실패/제외 기준을 함께 적는다.

## 7. 좌표 부호 검증

합성 `projectPoints → solvePnP` 테스트는 수학적 회전 복원을 검사하지만 실제 Face Landmarker·카메라 배치의 편향은 검사하지 못한다. 대상 장치에서 다음을 수행한다.

```bash
.venv/bin/python scripts/hardware_smoke.py --consent --guided-pose
```

- 정면 대비 화면 왼쪽으로 고개를 돌리면 yaw가 음수여야 한다.
- 화면 오른쪽은 yaw 양수, 위는 pitch 음수, 아래는 pitch 양수여야 한다.
- 중심 자세의 yaw/pitch 절댓값과 반복 표준편차를 기록한다.
- 브라우저가 미러 preview를 표시해도 API 수치는 원본 프레임 좌표 규약임을 확인한다.
- 캘리브레이션 전 gaze 좌/우와 캘리브레이션 후 zone을 각각 확인한다.
