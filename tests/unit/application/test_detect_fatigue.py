import numpy as np
import pytest

from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.value_objects import FatigueThresholds


def _landmarks(eye_open: float, mouth_open: float) -> FaceLandmarks:
    h_eye = eye_open / 2
    h_m = mouth_open / 2
    eye = (
        Point(0.0, 0.0), Point(0.3, -h_eye), Point(0.7, -h_eye),
        Point(1.0, 0.0), Point(0.7, h_eye), Point(0.3, h_eye),
    )
    mouth = (
        Point(0.0, 0.0), Point(0.15, -h_m), Point(0.35, -h_m), Point(0.5, -h_m),
        Point(0.65, -h_m), Point(0.85, -h_m), Point(1.0, 0.0), Point(0.85, h_m),
        Point(0.65, h_m), Point(0.5, h_m), Point(0.35, h_m), Point(0.15, h_m),
    )
    return FaceLandmarks(
        left_eye_contour=eye, right_eye_contour=eye,
        left_iris=None, right_iris=None,
        mouth_outer=mouth, mouth_inner=mouth,
        face_oval=tuple(Point(float(i), 0.0) for i in range(36)),
    )


class FakeDetector:
    def __init__(self, landmarks_list: list[FaceLandmarks]):
        self._ret = landmarks_list

    def detect(self, frame):
        return self._ret


def _frame() -> Frame:
    return Frame(image=np.zeros((2, 2, 3), dtype=np.uint8), timestamp=0.0, index=0)


class TestDetectFatigueUseCase:
    def test_returns_previous_state_when_no_face(self):
        uc = DetectFatigueUseCase(FakeDetector([]), FatigueThresholds())
        prev = FatigueState.initial()
        state, faces = uc.execute(_frame(), prev)
        assert state == prev
        assert faces == []

    def test_uses_first_face_when_multiple(self):
        lm1 = _landmarks(eye_open=0.1, mouth_open=0.1)
        lm2 = _landmarks(eye_open=0.5, mouth_open=0.1)
        uc = DetectFatigueUseCase(
            FakeDetector([lm1, lm2]),
            FatigueThresholds(ear_threshold=0.25, mar_threshold=0.6,
                              consecutive_frames=5, warning_ratio=0.8),
        )
        state, faces = uc.execute(_frame(), FatigueState.initial())
        assert state.severity == "warning"
        assert len(faces) == 2

    def test_open_eyes_stay_normal(self):
        lm = _landmarks(eye_open=0.5, mouth_open=0.1)
        uc = DetectFatigueUseCase(FakeDetector([lm]), FatigueThresholds())
        state, _ = uc.execute(_frame(), FatigueState.initial())
        assert state.severity == "normal"
