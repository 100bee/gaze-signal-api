# 제품명 결정 기록

프로젝트의 공개 이름은 **GazeSignal API**, 저장소 이름은 `gaze-signal-api`, Python import
package는 `gaze_signal_api`로 정했다.

## 선택 이유

- `gaze`는 프로젝트가 직접 관찰하는 핵심 신호를 나타낸다.
- `signal`은 결과가 사람에 대한 판단이 아니라 파생 센서 데이터라는 경계를 드러낸다.
- `API`는 독립된 판정 제품보다 다른 애플리케이션에 통합하는 기반 계층임을 설명한다.
- Focus, Attention, Integrity, Trust, Proctor, Score처럼 검증하지 않는 능력·의도를 암시하는
  단어를 피한다.

이 이름이 정밀 아이트래커 성능을 암시하지 않도록 모든 공개 설명에서 **webcam-based coarse
gaze estimation**이라는 범위를 함께 표시한다. 얼굴 존재, head pose, blink와 선택적 객체 감지는
시선 신호를 보완하는 시각 세션 신호로 설명한다.

공개 웹, GitHub, PyPI와 npm의 가벼운 충돌 검색에서는 `GazeSignal API`와 정확히 일치하는 대표
제품을 확인하지 못했다. `gaze signal` 자체는 시선 추적 분야의 일반 기술 용어다. 이 기록은
법률상 상표 clearance가 아니며 상용 출시 전 별도 상표·도메인 검토가 필요하다.
