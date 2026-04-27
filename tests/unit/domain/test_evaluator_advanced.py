"""Testes do evaluator com calibração, histerese, cooldown e fala-vs-bocejo."""
import pytest

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Point
from driver_fatigue.domain.evaluator import evaluate_fatigue
from driver_fatigue.domain.value_objects import (
    CalibrationSettings,
    FatigueThresholds,
    FrameQuality,
    PersonalBaseline,
)


def _eye(open_ratio: float):
    h = open_ratio / 2
    return (
        Point(0.0, 0.0), Point(0.3, -h), Point(0.7, -h),
        Point(1.0, 0.0), Point(0.7, h), Point(0.3, h),
    )


def _mouth(open_ratio: float):
    h = open_ratio / 2
    return (
        Point(0.0, 0.0), Point(0.15, -h), Point(0.35, -h), Point(0.5, -h),
        Point(0.65, -h), Point(0.85, -h), Point(1.0, 0.0), Point(0.85, h),
        Point(0.65, h), Point(0.5, h), Point(0.35, h), Point(0.15, h),
    )


def _landmarks(eye_open: float, mouth_open: float):
    return FaceLandmarks(
        left_eye_contour=_eye(eye_open), right_eye_contour=_eye(eye_open),
        left_iris=None, right_iris=None,
        mouth_outer=_mouth(mouth_open), mouth_inner=_mouth(mouth_open),
        face_oval=tuple(Point(float(i), 0.0) for i in range(36)),
    )


class TestUntrustedFrameSkipped:
    def test_untrusted_quality_returns_previous_state(self):
        prev = FatigueState.initial()
        bad = FrameQuality.untrusted("test")
        result = evaluate_fatigue(_landmarks(0.1, 0.1), FatigueThresholds(), prev, quality=bad)
        # mantém severity normal e consecutive 0; só atualiza quality
        assert result.severity == "normal"
        assert result.consecutive_frames == 0
        assert result.quality.trustworthy is False
        assert result.quality.reason == "test"


class TestCalibration:
    def test_warmup_inhibits_alert(self):
        cal = CalibrationSettings(enabled=True, warmup_frames=10)
        thresh = FatigueThresholds(
            ear_threshold=0.25, mar_threshold=0.6,
            consecutive_frames=3, warning_ratio=0.8,
        )
        state = FatigueState.initial()
        # 5 frames com olho fechado durante warmup → não dispara
        for _ in range(5):
            state = evaluate_fatigue(
                _landmarks(0.05, 0.1), thresh, state, calibration=cal,
            )
        assert state.severity == "normal"
        assert state.baseline.sample_count == 5

    def test_calibration_completes_then_uses_relative_threshold(self):
        cal = CalibrationSettings(
            enabled=True, warmup_frames=20, ear_close_ratio=0.5,
        )
        thresh = FatigueThresholds(
            ear_threshold=0.001, mar_threshold=10.0,
            consecutive_frames=3, warning_ratio=1.0,
        )
        state = FatigueState.initial()
        # warmup com EAR alto (~ratio 0.4 → EAR ~0.4)
        for _ in range(20):
            state = evaluate_fatigue(
                _landmarks(0.4, 0.05), thresh, state, calibration=cal,
            )
        assert state.baseline.is_calibrated(20)
        # Agora 1 frame com olho fechado bem abaixo de 0.5*baseline_ear:
        # EAR atual ~0.05, baseline_ear ~0.4, threshold = 0.4*0.5 = 0.2 → 0.05 < 0.2
        state = evaluate_fatigue(
            _landmarks(0.05, 0.05), thresh, state, calibration=cal,
        )
        assert state.consecutive_frames == 1


class TestHysteresisRecovery:
    def test_alert_does_not_drop_until_recovery_frames(self):
        thresh = FatigueThresholds(
            ear_threshold=0.25, mar_threshold=0.6,
            consecutive_frames=3, warning_ratio=1.0,
            recovery_frames=4,
        )
        state = FatigueState.initial()
        for _ in range(3):
            state = evaluate_fatigue(_landmarks(0.05, 0.1), thresh, state)
        assert state.severity == "alert"
        # 3 frames limpos < recovery_frames(4) → ainda alert
        for _ in range(3):
            state = evaluate_fatigue(_landmarks(0.5, 0.1), thresh, state)
        assert state.severity == "alert"
        # 4º frame limpo → sai
        state = evaluate_fatigue(_landmarks(0.5, 0.1), thresh, state)
        assert state.severity == "normal"


class TestCooldown:
    def test_cooldown_keeps_warning_within_window(self):
        thresh = FatigueThresholds(
            ear_threshold=0.25, mar_threshold=0.6,
            consecutive_frames=2, warning_ratio=1.0,
            recovery_frames=1,
            alarm_cooldown_seconds=10.0,
        )
        state = FatigueState.initial()
        # primeiro alarme em t=1.0
        state = evaluate_fatigue(_landmarks(0.05, 0.1), thresh, state, timestamp=0.5)
        state = evaluate_fatigue(_landmarks(0.05, 0.1), thresh, state, timestamp=1.0)
        assert state.severity == "alert"
        # recovery em t=1.5
        state = evaluate_fatigue(_landmarks(0.5, 0.1), thresh, state, timestamp=1.5)
        assert state.severity == "normal"
        # nova suspeita em t=2.0 (dentro do cooldown de 10s)
        state = evaluate_fatigue(_landmarks(0.05, 0.1), thresh, state, timestamp=2.0)
        state = evaluate_fatigue(_landmarks(0.05, 0.1), thresh, state, timestamp=2.5)
        # alert_cutoff alcançado, mas dentro do cooldown → fica em warning
        assert state.severity == "warning"

    def test_cooldown_expires_allows_new_alert(self):
        thresh = FatigueThresholds(
            ear_threshold=0.25, mar_threshold=0.6,
            consecutive_frames=2, warning_ratio=1.0,
            recovery_frames=1,
            alarm_cooldown_seconds=2.0,
        )
        state = FatigueState.initial()
        state = evaluate_fatigue(_landmarks(0.05, 0.1), thresh, state, timestamp=0.0)
        state = evaluate_fatigue(_landmarks(0.05, 0.1), thresh, state, timestamp=0.5)
        state = evaluate_fatigue(_landmarks(0.5, 0.1), thresh, state, timestamp=1.0)
        # Após cooldown (t=10), nova suspeita pode alertar
        state = evaluate_fatigue(_landmarks(0.05, 0.1), thresh, state, timestamp=10.0)
        state = evaluate_fatigue(_landmarks(0.05, 0.1), thresh, state, timestamp=10.5)
        assert state.severity == "alert"


class TestYawnVsSpeech:
    def test_unstable_mar_window_does_not_count_as_yawn(self):
        # janela cheia oscilando → fala
        thresh = FatigueThresholds(
            ear_threshold=0.25, mar_threshold=0.5,
            consecutive_frames=10, warning_ratio=1.0,
            yawn_window_frames=5,
            yawn_stability_max=0.05,
        )
        state = FatigueState.initial()
        # Olhos abertos, MAR oscila entre 0.55 e 0.95 (alta variância)
        mars = [0.55, 0.95, 0.55, 0.95, 0.55, 0.95]
        for m in mars:
            state = evaluate_fatigue(_landmarks(0.5, m), thresh, state)
        # Janela cheia, alta std → não deve contar como bocejo
        assert state.consecutive_frames < 5

    def test_stable_high_mar_counts_as_yawn(self):
        thresh = FatigueThresholds(
            ear_threshold=0.25, mar_threshold=0.5,
            consecutive_frames=10, warning_ratio=1.0,
            yawn_window_frames=5,
            yawn_stability_max=0.05,
        )
        state = FatigueState.initial()
        # MAR bem alto e estável → bocejo
        for _ in range(7):
            state = evaluate_fatigue(_landmarks(0.5, 0.95), thresh, state)
        assert state.consecutive_frames >= 5
