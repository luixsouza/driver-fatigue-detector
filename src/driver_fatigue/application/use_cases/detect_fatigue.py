from __future__ import annotations

import dataclasses
import threading

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
        # Thresholds podem ser ajustados em runtime pela UI (sliders).
        # Lock protege contra leitura durante reconfiguração.
        self._thresholds_lock = threading.Lock()

    @property
    def thresholds(self) -> FatigueThresholds:
        with self._thresholds_lock:
            return self._thresholds

    def update_thresholds(self, **fields) -> FatigueThresholds:
        """Substitui thresholds em runtime. Aceita subset dos campos de
        FatigueThresholds; ignora keys desconhecidas. Retorna o estado final."""
        valid = {f.name for f in dataclasses.fields(FatigueThresholds)}
        filtered = {k: v for k, v in fields.items() if k in valid and v is not None}
        if not filtered:
            return self._thresholds
        with self._thresholds_lock:
            self._thresholds = dataclasses.replace(self._thresholds, **filtered)
            return self._thresholds

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
        with self._thresholds_lock:
            current_thresholds = self._thresholds
        new_state = evaluate_fatigue(
            faces[0],
            current_thresholds,
            previous,
            calibration=self._calibration,
            quality=quality,
            timestamp=frame.timestamp,
        )
        return new_state, faces
