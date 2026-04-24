import pytest

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Point
from driver_fatigue.domain.evaluator import evaluate_fatigue
from driver_fatigue.domain.value_objects import FatigueThresholds


def _eye(open_ratio: float) -> tuple[Point, ...]:
    h = open_ratio / 2
    return (
        Point(0.0, 0.0), Point(0.3, -h), Point(0.7, -h),
        Point(1.0, 0.0), Point(0.7, h),  Point(0.3, h),
    )


def _mouth(open_ratio: float) -> tuple[Point, ...]:
    h = open_ratio / 2
    return (
        Point(0.0, 0.0), Point(0.15, -h), Point(0.35, -h), Point(0.5, -h),
        Point(0.65, -h), Point(0.85, -h), Point(1.0, 0.0), Point(0.85, h),
        Point(0.65, h), Point(0.5, h), Point(0.35, h), Point(0.15, h),
    )


def _landmarks(eye_open: float, mouth_open: float) -> FaceLandmarks:
    return FaceLandmarks(
        left_eye_contour=_eye(eye_open),
        right_eye_contour=_eye(eye_open),
        left_iris=None, right_iris=None,
        mouth_outer=_mouth(mouth_open),
        mouth_inner=_mouth(mouth_open * 0.5),
        face_oval=tuple(Point(float(i), 0.0) for i in range(36)),
    )


THRESH = FatigueThresholds(
    ear_threshold=0.25, mar_threshold=0.60,
    consecutive_frames=5, warning_ratio=0.8,
)


class TestEvaluateFatigue:
    def test_open_eyes_no_yawn_is_normal(self):
        lm = _landmarks(eye_open=0.4, mouth_open=0.1)
        result = evaluate_fatigue(lm, THRESH, FatigueState.initial())
        assert result.severity == "normal"
        assert result.is_fatigued is False
        assert result.consecutive_frames == 0

    def test_closed_eyes_increment_counter(self):
        lm = _landmarks(eye_open=0.1, mouth_open=0.1)
        result = evaluate_fatigue(lm, THRESH, FatigueState.initial())
        assert result.consecutive_frames == 1
        assert result.severity == "warning"

    def test_counter_reaches_threshold_triggers_alert(self):
        lm = _landmarks(eye_open=0.1, mouth_open=0.1)
        state = FatigueState.initial()
        for _ in range(5):
            state = evaluate_fatigue(lm, THRESH, state)
        assert state.consecutive_frames == 5
        assert state.severity == "alert"
        assert state.is_fatigued is True

    def test_yawn_also_increments_counter(self):
        lm = _landmarks(eye_open=0.4, mouth_open=0.8)
        result = evaluate_fatigue(lm, THRESH, FatigueState.initial())
        assert result.consecutive_frames == 1
        assert result.is_yawning is True

    def test_open_eyes_reset_counter_back_to_normal(self):
        lm_closed = _landmarks(eye_open=0.1, mouth_open=0.1)
        lm_open = _landmarks(eye_open=0.4, mouth_open=0.1)
        state = FatigueState.initial()
        for _ in range(5):
            state = evaluate_fatigue(lm_closed, THRESH, state)
        assert state.severity == "alert"
        state = evaluate_fatigue(lm_open, THRESH, state)
        assert state.severity == "normal"
        assert state.consecutive_frames == 0
        assert state.is_fatigued is False

    def test_warning_fires_before_alert(self):
        lm = _landmarks(eye_open=0.1, mouth_open=0.1)
        state = FatigueState.initial()
        state = evaluate_fatigue(lm, THRESH, state)  # 1
        assert state.severity == "warning"
        state = evaluate_fatigue(lm, THRESH, state)  # 2
        state = evaluate_fatigue(lm, THRESH, state)  # 3
        state = evaluate_fatigue(lm, THRESH, state)  # 4
        assert state.severity == "alert"
