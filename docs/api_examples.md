# API 예시

전체 스키마와 validation은 실행 중 `/docs`에서 확인한다. 아래 응답은 설명을 위한 예다.

## 세션 생성과 시작

```http
POST /sessions
Content-Type: application/json

{
  "consent_given": true,
  "camera_index": 0,
  "frame_width": 640,
  "frame_height": 480,
  "target_fps": 15,
  "screen_width": 1512,
  "screen_height": 982,
  "yolo_enabled": false,
  "calibration_id": null
}
```

```json
{
  "id": "8bf3de9a-f0d8-45c2-a719-07bcb8962fb4",
  "status": "created",
  "consent_given": true,
  "camera_index": 0,
  "frame_width": 640,
  "frame_height": 480,
  "target_fps": 15.0,
  "screen_width": 1512,
  "screen_height": 982,
  "yolo_enabled": false,
  "calibration_id": null,
  "created_at": "2026-09-04T01:23:40Z",
  "started_at": null,
  "stopped_at": null,
  "failure_code": null
}
```

`POST /sessions/{id}/start` 후 WebSocket `/ws/sessions/{id}`에 연결한다.

## 실시간 파생 이벤트

```json
{
  "session_id": "8bf3de9a-f0d8-45c2-a719-07bcb8962fb4",
  "timestamp": "2026-09-04T01:23:45.123Z",
  "face_present": true,
  "face_analysis_available": true,
  "gaze_zone": "center",
  "gaze_feature_x": 0.51,
  "gaze_feature_y": 0.48,
  "head_yaw": -4.2,
  "head_pitch": 7.1,
  "head_roll": 0.8,
  "blink_detected": false,
  "phone_visible": false,
  "state": "screen_facing",
  "confidence": 0.87,
  "processing_latency_ms": 38.4
}
```

`looking_away`는 관찰 상태일 뿐 부정행위나 집중도 판정이 아니다.

## Calibration 생성

아래는 구조를 줄인 예다. 실제로는 서로 다른 5/9 target과 target별 복수 sample을 권장한다.

```json
{
  "label": "MacBook desk setup",
  "pattern_points": 5,
  "camera_index": 0,
  "camera_width": 640,
  "camera_height": 480,
  "screen_width": 1512,
  "screen_height": 982,
  "samples": [
    {"target_x": 0.5, "target_y": 0.5, "feature_x": 0.51, "feature_y": 0.49, "confidence": 0.91},
    {"target_x": 0.1, "target_y": 0.5, "feature_x": 0.31, "feature_y": 0.50, "confidence": 0.88},
    {"target_x": 0.9, "target_y": 0.5, "feature_x": 0.69, "feature_y": 0.50, "confidence": 0.90},
    {"target_x": 0.5, "target_y": 0.1, "feature_x": 0.50, "feature_y": 0.35, "confidence": 0.87},
    {"target_x": 0.5, "target_y": 0.9, "feature_x": 0.50, "feature_y": 0.67, "confidence": 0.89}
  ]
}
```

## 안전한 오류

```json
{
  "error": {
    "code": "camera_consent_required",
    "message": "explicit camera consent is required before start"
  }
}
```

예상 가능한 오류는 403/404/409/503과 안정적인 code를 사용한다. 500 응답에는 traceback이나 로컬 파일 경로가 없다.
