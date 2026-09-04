from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from gaze_signal_api.analytics.smoothing import ExponentialMovingAverage, ZoneMajoritySmoother
from gaze_signal_api.config.settings import Settings
from gaze_signal_api.errors import ResourceUnavailableError
from gaze_signal_api.schemas.analysis import FrameSignals, HeadPose
from gaze_signal_api.schemas.calibration import CalibrationParameters
from gaze_signal_api.schemas.common import GazeZone, utc_now
from gaze_signal_api.vision.face_landmarks import FaceLandmarkExtractor
from gaze_signal_api.vision.gaze_estimator import GazeEstimator, eye_aspect_ratio
from gaze_signal_api.vision.head_pose import HeadPoseEstimator
from gaze_signal_api.vision.object_detector import PhoneDetector

logger = logging.getLogger(__name__)


class VisionPipeline:
    """Frame-local signal extraction with independently degradable components."""

    def __init__(
        self,
        settings: Settings,
        *,
        calibration: CalibrationParameters | None = None,
        yolo_enabled: bool | None = None,
        face_extractor: FaceLandmarkExtractor | None = None,
    ) -> None:
        self.settings = settings
        self.calibration = calibration
        self.face_extractor = face_extractor or FaceLandmarkExtractor(
            settings.face_model_path, settings.face_detection_confidence
        )
        self.head_pose = HeadPoseEstimator()
        self.gaze = GazeEstimator(
            calibration,
            settings.head_yaw_away_degrees,
            settings.head_pitch_away_degrees,
        )
        self.phone = PhoneDetector(
            enabled=settings.yolo_enabled if yolo_enabled is None else yolo_enabled,
            model_path=settings.yolo_model_path,
            confidence_threshold=settings.yolo_confidence,
            every_n_frames=settings.yolo_every_n_frames,
        )
        self.yaw_ema = ExponentialMovingAverage(settings.ema_alpha)
        self.pitch_ema = ExponentialMovingAverage(settings.ema_alpha)
        self.roll_ema = ExponentialMovingAverage(settings.ema_alpha)
        self.zone_smoother = ZoneMajoritySmoother(window_size=5)
        self._eyes_closed = False
        self._face_failure_reported = False
        self._frame_index = 0

    def process(self, frame_bgr: Any) -> FrameSignals:
        started = perf_counter()
        timestamp = utc_now()
        self._frame_index += 1
        phone_visible = self.phone.detect(frame_bgr, self._frame_index)

        analysis_available = True
        try:
            observation = self.face_extractor.extract(frame_bgr)
        except ResourceUnavailableError as exc:
            if not self._face_failure_reported:
                logger.warning("face analysis unavailable: %s", exc.message)
                self._face_failure_reported = True
            analysis_available = False
            observation = None
        except Exception:
            logger.exception("face analysis failed for a frame")
            analysis_available = False
            observation = None

        if observation is None:
            self._reset_face_state()
            return FrameSignals(
                timestamp=timestamp,
                face_present=False,
                face_analysis_available=analysis_available,
                gaze_zone=GazeZone.UNKNOWN,
                phone_visible=phone_visible,
                confidence=0.0,
                processing_latency_ms=(perf_counter() - started) * 1000.0,
            )

        height, width = frame_bgr.shape[:2]
        pose = self.head_pose.estimate(observation.landmarks, width, height) or HeadPose()
        smoothed_pose = HeadPose(
            yaw=self.yaw_ema.update(pose.yaw),
            pitch=self.pitch_ema.update(pose.pitch),
            roll=self.roll_ema.update(pose.roll),
        )
        relative_pose = self._relative_pose(smoothed_pose)
        gaze = self.gaze.estimate(observation.landmarks, relative_pose, observation.confidence)
        zone = self.zone_smoother.update(gaze.zone)
        ear = eye_aspect_ratio(observation.landmarks)
        eyes_closed = ear is not None and ear < self.settings.blink_ear_threshold
        blink_detected = eyes_closed and not self._eyes_closed
        self._eyes_closed = eyes_closed

        return FrameSignals(
            timestamp=timestamp,
            face_present=True,
            gaze_zone=zone,
            gaze_feature_x=gaze.feature_x,
            gaze_feature_y=gaze.feature_y,
            head_yaw=relative_pose.yaw,
            head_pitch=relative_pose.pitch,
            head_roll=relative_pose.roll,
            blink_detected=blink_detected,
            phone_visible=phone_visible,
            confidence=gaze.confidence,
            processing_latency_ms=(perf_counter() - started) * 1000.0,
        )

    def _reset_face_state(self) -> None:
        self.yaw_ema.reset()
        self.pitch_ema.reset()
        self.roll_ema.reset()
        self.zone_smoother.reset()
        self._eyes_closed = False

    def _relative_pose(self, pose: HeadPose) -> HeadPose:
        if self.calibration is None:
            return pose
        return HeadPose(
            yaw=pose.yaw - self.calibration.neutral_head_yaw,
            pitch=pose.pitch - self.calibration.neutral_head_pitch,
            roll=pose.roll - self.calibration.neutral_head_roll,
        )

    def close(self) -> None:
        self.face_extractor.close()
