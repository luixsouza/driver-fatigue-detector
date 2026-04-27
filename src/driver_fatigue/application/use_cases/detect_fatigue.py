from __future__ import annotations

from driver_fatigue.application.ports import FaceDetectorPort
from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueState,
    Frame,
)
from driver_fatigue.domain.evaluator import evaluate_fatigue
from driver_fatigue.domain.quality import estimate_quality
from driver_fatigue.domain.value_objects import (
    CalibrationSettings,
    FatigueThresholds,
    FrameQualityPolicy,
)


class DetectFatigueUseCase:
    def __init__(
        self,
        detector: FaceDetectorPort,
        thresholds: FatigueThresholds,
        *,
        calibration: CalibrationSettings | None = None,
        quality_policy: FrameQualityPolicy | None = None,
    ) -> None:
        self._detector = detector
        self._thresholds = thresholds
        self._calibration = calibration or CalibrationSettings(enabled=False)
        self._quality_policy = quality_policy or FrameQualityPolicy()

    def execute(
        self,
        frame: Frame,
        previous: FatigueState,
    ) -> tuple[FatigueState, list[FaceLandmarks]]:
        faces = self._detector.detect(frame)
        if not faces:
            return previous, faces
        h, w = frame.image.shape[:2]
        quality = estimate_quality(
            faces[0],
            frame_width=w,
            frame_height=h,
            policy=self._quality_policy,
        )
        new_state = evaluate_fatigue(
            faces[0],
            self._thresholds,
            previous,
            calibration=self._calibration,
            quality=quality,
            timestamp=frame.timestamp,
        )
        return new_state, faces
