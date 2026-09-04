# 요구사항과 MVP 범위

## 제품 정의

GazeSignal API는 웹·데스크톱 애플리케이션이 로컬 분석 프로세스와 연동할 수 있는 **시각 세션 신호 API**다. “집중”, 정직성, 규정 위반, 감정, 역량을 추론하지 않으며 사람에 대한 점수·순위·자동 불이익 결정을 제공하지 않는다.

### 사용자

- 사용자: 명시적으로 카메라 사용에 동의하고, 작동 상태를 항상 확인하며, 자신의 데이터를 삭제할 수 있다.
- 플랫폼 개발자: 세션 상태와 관찰 신호를 REST/WebSocket으로 통합한다.
- 검증 담당자: 합성 데이터와 동의 받은 별도 실험으로 정확도·지연·실패율을 측정한다.

## 기능 요구사항 추적

| 영역 | MVP 구현 | 검증 |
|---|---|---|
| 세션 CRUD/상태 전환 | `/sessions` 및 start/stop/summary | 통합 테스트 |
| 카메라 선택/설정/실패 | camera index, 해상도, FPS, 동의가 필요한 `/cameras` | mock + 실제 기기 필요 |
| 자원 해제/재연결 | capture/analysis thread 종료, 제한 재시도 | mock; macOS 실기기 필요 |
| 5/9점 캘리브레이션 | 품질 가중 affine fit, 중립 pose offset, 저장/조회/삭제 | 합성 좌표 테스트 |
| 설정 변경 감지 | 카메라·프레임·화면 geometry 완전 일치 | API 409 테스트 |
| 프레임 신호 | face, zone, pose, blink, phone, confidence, latency | 순수 함수/mock 테스트 |
| 불확실성 | `unknown`, `face_analysis_available`, 낮은 confidence | 기능 저하 테스트 |
| 시간축 분석 | EMA, zone majority, debounce, away minimum | 단위 테스트 |
| 독립 YOLO | on/off, threshold, N-frame 주기, failure isolation | 모듈 테스트/실기기 필요 |
| 이벤트 저장/요약 | SQLite WAL events/transitions, 요구 통계 | 동시 write 통합/요약 테스트 |
| WebSocket | 세션별 latest-event fan-out | 통합 테스트 |
| backpressure | capture와 analysis 사이 size-one buffer | 단위 테스트 |
| 개인정보 | 원본 저장/전송 경로 없음, 동의, 삭제 | 코드/설정/API 테스트 |

## 상태 의미

- `screen_facing`: 신뢰 가능한 gaze zone이 화면 안(center/left/right/up/down)에 있다.
- `looking_away`: `away` 후보가 설정된 최소 시간 이상 지속됐다.
- `face_missing`: 얼굴 분석기는 정상이나 얼굴이 지속적으로 검출되지 않았다.
- `unknown`: 모델 미가용, 눈 특징 불량, 낮은 confidence 등으로 분류할 수 없다.

이 상태들은 사람에 대한 판정이 아니라 센서 출력이다. 특히 `looking_away`는 부정행위를 뜻하지 않는다.

## 비기능 목표

- 기본 비전 파이프라인 15 FPS 이상 목표(대상 노트북별 측정 전에는 보장 아님)
- WebSocket 파생 이벤트 지연 p95 300 ms 이하 목표
- 캡처 큐는 한 프레임으로 제한하고 오래된 프레임을 폐기
- SQLite와 카메라/모델 종료 자원 정리
- 공개 응답에는 내부 경로·traceback 미노출
- 환경 변수 중앙 설정, 잘못된 범위 거부
- macOS 우선, OpenCV adapter 밖에 플랫폼 분기 없음

## 명시적 비범위

- 집중력, 감정, 신원, 성격, 역량, 부정행위 여부 추론
- 얼굴 인식/등록, 음성 분석, 화면 녹화, 키 입력, 창 제목 수집
- 사람에 대한 자동 결정, 위험 점수, 사용자 순위
- 의료·접근성 진단, 학생/직원 상시 감시
- 원격 원본 영상 저장 또는 업로드
- 검증되지 않은 정확도/FPS 숫자를 제품 성능으로 주장

## 수용 기준

1. 핵심·개발 의존성만 설치한 headless 환경에서 테스트와 Ruff가 통과한다.
2. MediaPipe/YOLO 미설치가 REST 서버 부팅을 막지 않는다.
3. 동의 없는 start와 camera probe는 403, 중복/잘못된 상태 전환은 409다.
4. 카메라 시작 실패는 503과 안전한 오류 코드만 노출한다.
5. 이벤트/캘리브레이션/세션 삭제가 DB에 반영된다.
6. 실기기 확인 전 정량 정확도 주장을 하지 않는다.
