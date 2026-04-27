"""Testes do EyeStateContextValidator (modo PERCLOS-only — sem ONNX)."""
import numpy as np
import pytest

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.value_objects import PersonalBaseline
from driver_fatigue.infrastructure.context_validators.eye_state_onnx import (
    EyeStateContextValidator,
)


def _frame(ts: float):
    return Frame(image=np.zeros((10, 10, 3), dtype=np.uint8), timestamp=ts, index=int(ts))


def _landmarks():
    eye = (Point(0, 0), Point(0.3, -0.2), Point(0.7, -0.2),
           Point(1, 0), Point(0.7, 0.2), Point(0.3, 0.2))
    mouth = tuple(Point(float(i), 0) for i in range(12))
    return FaceLandmarks(
        left_eye_contour=eye, right_eye_contour=eye,
        left_iris=None, right_iris=None,
        mouth_outer=mouth, mouth_inner=mouth[:8],
        face_oval=tuple(Point(float(i), 0) for i in range(36)),
    )


def _state(ear: float, baseline_count: int = 60, baseline_ear: float = 0.30):
    base = PersonalBaseline(
        ear_rest=baseline_ear, mar_rest=0.20,
        ear_std=0.02, mar_std=0.02,
        sample_count=baseline_count,
    )
    return FatigueState(
        ear=ear, mar=0.2,
        consecutive_frames=20, is_fatigued=True, is_yawning=False,
        severity="alert", recovery_frames=0, last_alert_timestamp=0.0,
        baseline=base, quality=FatigueState.initial().quality, mar_window=(),
    )


class TestPerclosOnly:
    def test_insufficient_samples_confirms(self):
        v = EyeStateContextValidator(
            perclos_window_seconds=60.0,
            perclos_threshold=0.4,
            min_perclos_samples=30,
        )
        verdict = v.confirm_drowsy(_frame(0.0), _landmarks(), _state(ear=0.1))
        assert verdict.drowsy is True
        assert "insufficient" in verdict.reason

    def test_high_perclos_confirms_drowsy(self):
        v = EyeStateContextValidator(
            perclos_window_seconds=60.0,
            perclos_threshold=0.4,
            min_perclos_samples=10,
        )
        # 10 frames com EAR baixo (closed)
        for i in range(10):
            v.confirm_drowsy(_frame(i * 0.1), _landmarks(), _state(ear=0.1))
        verdict = v.confirm_drowsy(_frame(1.0), _landmarks(), _state(ear=0.1))
        assert verdict.drowsy is True
        assert "PERCLOS" in verdict.reason

    def test_low_perclos_rejects(self):
        v = EyeStateContextValidator(
            perclos_window_seconds=60.0,
            perclos_threshold=0.4,
            min_perclos_samples=10,
        )
        # 10 frames com olho aberto (EAR alto > 0.75 * baseline 0.30 = 0.225)
        for i in range(10):
            v.confirm_drowsy(_frame(i * 0.1), _landmarks(), _state(ear=0.3))
        verdict = v.confirm_drowsy(_frame(1.0), _landmarks(), _state(ear=0.3))
        assert verdict.drowsy is False

    def test_invalid_threshold(self):
        with pytest.raises(ValueError):
            EyeStateContextValidator(perclos_threshold=0.0)
        with pytest.raises(ValueError):
            EyeStateContextValidator(perclos_threshold=1.0)


class TestNonexistentModelPath:
    def test_missing_model_falls_back_to_perclos(self, tmp_path):
        v = EyeStateContextValidator(
            model_path=tmp_path / "missing.onnx",
            perclos_window_seconds=60.0,
            perclos_threshold=0.4,
            min_perclos_samples=10,
        )
        # Apenas confirma que constrói e roda em modo PERCLOS-only
        for i in range(15):
            v.confirm_drowsy(_frame(i * 0.1), _landmarks(), _state(ear=0.1))
        verdict = v.confirm_drowsy(_frame(2.0), _landmarks(), _state(ear=0.1))
        assert verdict.drowsy is True
