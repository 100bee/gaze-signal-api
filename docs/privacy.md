# 개인정보·윤리 경계

## 데이터 흐름과 보존

GazeSignal API는 카메라 프레임을 로컬 메모리에서만 처리한다. 최신 한 프레임을 넘는 backlog를 만들지 않고 처리 후 참조를 버린다. 원본/크롭/landmark overlay를 DB, API, WebSocket, 로그, 외부 서비스로 보내지 않는다.

저장되는 항목은 다음 파생 데이터뿐이다.

- 세션 ID와 시작/종료 시각
- 얼굴 검출 여부와 분석기 가용 여부
- 거친 gaze zone과 calibration용 정규화 eye feature
- head yaw/pitch/roll, blink edge, phone visibility
- 상태 enum, confidence, 처리 지연
- 캘리브레이션 계수, geometry, 오차 요약

eye feature와 head pose도 개인 관련 데이터로 취급해야 한다. 기본 SQLite 파일 접근 권한과 보존 기간은 통합 플랫폼의 책임이며, 필요 기간이 끝나면 DELETE API로 지운다.

API의 `confidence`는 개인별로 확률 보정된 정확도나 진실 가능성이 아니다. 모델 가용성과 캘리브레이션 학습 오차에 기반한 휴리스틱 품질 게이트일 뿐이며 사람에 대한 점수나 고위험 의사결정의 가중치로 사용하지 않는다.

## 동의와 표시

- `POST /sessions`는 `consent_given` 선택을 명시적으로 받는다.
- false인 세션은 카메라를 시작할 수 없다.
- 카메라 열거도 장치를 활성화할 수 있으므로 `/cameras`는 `consent=true` 없이는 거부한다.
- 기본 콘솔은 분석 중 표시를 화면 상단에 계속 보여준다.
- 동의 문구에는 로컬 처리, 저장 항목, 목적, 중지·삭제 방법을 포함해야 한다.
- 동의를 철회하면 즉시 stop 후 delete해야 한다.

## 통합 시 금지하는 해석

이 시스템은 다음을 판단할 근거가 아니다.

- 사용자의 집중도, 정직성, 불안, 감정, 인지 능력, 성격
- `looking_away`나 `phone_visible`만으로 부정행위 여부
- 얼굴 부재만으로 시험 포기·대리 응시 여부
- 사람에 대한 점수, 순위, 자동 불이익, 차별적 위험 분류

관찰 신호에는 정상적인 설명이 많다. 문제 메모를 보거나 접근성 장치를 사용하거나 보호자/통역을 확인하거나 카메라가 흔들릴 수 있다. 사람의 중요한 결정을 자동화하지 말고, 신호를 제공해야 한다면 사전 고지·이의 제기·접근성 예외·사람의 맥락 검토를 제공한다.

## 의도적으로 수집하지 않는 것

- 얼굴 embedding, 이름, 계정 신원, 얼굴 인식 결과
- 감정/인종/성별/연령/장애 추론
- 오디오, 키 입력, 클립보드, 창 제목, 화면 픽셀/내용
- 원본 카메라 영상과 스크린샷
- 외부 analytics/telemetry endpoint

## 위협과 완화

| 위협 | MVP 완화 | 배포자가 추가할 것 |
|---|---|---|
| 카메라 몰래 작동 | explicit consent + 지속 UI 표시 | OS 권한 안내, 접근 로그 |
| 원본 노출 | 저장/전송 코드 없음, memory-only queue | crash dump/화면 녹화 정책 확인 |
| 장기 행동 프로파일 | session scope와 delete API | 짧은 retention, 사용자 export/delete UI |
| DB 파일 탈취 | 외부 bind 기본 금지 | 디스크 암호화, 파일 권한, 계정 격리 |
| localhost API 악용 | JSON CORS·WebSocket Origin allowlist | 통합 사이트 origin 명시, 인증/TLS |
| 차별/오판 | 점수·자동 판정 없음 | DPIA/법률 검토, 사람 검토, 이의 절차 |
| 공급망/telemetry | 모델/패키지 선택 설치 | MediaPipe 고지 검토, checksum/SBOM |

## 모델/라이브러리 고지

MediaPipe Tasks 문서는 처리가 기기에서 일어난다고 설명하지만 성능·사용량 metrics 관련 개인정보 고지도 포함한다. 배포 전 해당 버전의 공식 고지와 관할 법률에 맞는 동의 문구를 검토한다. Ultralytics weight는 별도 스크립트에서 고정 URL과 SHA-256으로 사전 배치하며 런타임 자동 다운로드는 차단한다. 완전 오프라인 환경에서는 설치 단계 이후 네트워크도 차단한다.

## 삭제 의미

- `DELETE /sessions/{id}`: 세션, frame-derived events, state transitions 삭제
- `DELETE /calibrations/{id}`: affine 계수와 geometry 삭제
- SQLite는 삭제 페이지를 즉시 덮어쓰지 않을 수 있다. 높은 삭제 보장이 필요하면 종료 후 `VACUUM`, 암호화 키 폐기, 백업 보존 정책을 운영 절차에 포함한다.

기본 서버는 localhost 전용이고 인증을 제공하지 않는다. 다른 기기에 노출하거나 원격 통합 환경에서 운영하려면 reverse proxy의 TLS, 세션별 단기 인증 토큰, 요청 rate limit, 감사 로그를 먼저 추가해야 한다. 허용 origin은 `GAZE_SIGNAL_ALLOWED_ORIGINS`로 명시한다.

CORS와 WebSocket Origin 검사는 브라우저 경계를 줄일 뿐 인증이 아니다. 같은 컴퓨터의 다른 프로세스나 `curl`은 localhost API를 호출할 수 있고, `consent_given=true`가 실제 동의 UI를 거쳤는지도 서버 단독으로 증명하지 못한다. 통합 플랫폼은 동의 문구 버전·시각·철회 흐름을 자체 인증 사용자와 묶고, API에는 단기 세션 권한을 추가해야 한다.
