from __future__ import annotations

from driver_fatigue.application.ports import FaceDetectorPort
from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueState,
    Frame,
)
from driver_fatigue.domain.evaluator import evaluate_fatigue
from driver_fatigue.domain.value_objects import FatigueThresholds


class DetectFatigueUseCase:
    def __init__(
        self,
        detector: FaceDetectorPort,
        thresholds: FatigueThresholds,
    ) -> None:
        self._detector = detector
        self._thresholds = thresholds

    def execute(
        self,
        frame: Frame,
        previous: FatigueState,
    ) -> tuple[FatigueState, list[FaceLandmarks]]:
        faces = self._detector.detect(frame)
        if not faces:
            return previous, faces
        new_state = evaluate_fatigue(faces[0], self._thresholds, previous)
        return new_state, faces
