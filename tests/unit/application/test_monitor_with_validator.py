"""Testes do MonitorDriverUseCase com ContextValidator."""
import numpy as np

from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.application.use_cases.monitor_driver import MonitorDriverUseCase
from driver_fatigue.domain.entities import (
    FaceLandmarks,
    Frame,
    Point,
)
from driver_fatigue.domain.value_objects import ContextVerdict, FatigueThresholds


def _eye(open_ratio):
    h = open_ratio / 2
    return (Point(0, 0), Point(0.3, -h), Point(0.7, -h),
            Point(1, 0), Point(0.7, h), Point(0.3, h))


def _mouth(open_ratio):
    h = open_ratio / 2
    return (Point(0, 0), Point(0.15, -h), Point(0.35, -h), Point(0.5, -h),
            Point(0.65, -h), Point(0.85, -h), Point(1, 0), Point(0.85, h),
            Point(0.65, h), Point(0.5, h), Point(0.35, h), Point(0.15, h))


def _landmarks(eye_open, mouth_open):
    return FaceLandmarks(
        left_eye_contour=_eye(eye_open), right_eye_contour=_eye(eye_open),
        left_iris=None, right_iris=None,
        mouth_outer=_mouth(mouth_open), mouth_inner=_mouth(mouth_open),
        face_oval=tuple(Point(float(i), 0) for i in range(36)),
    )


class FakeSource:
    def __init__(self, n):
        self._remaining = n
        self._i = 0

    def read(self):
        if self._remaining <= 0:
            return None
        self._remaining -= 1
        self._i += 1
        return Frame(image=np.zeros((4, 4, 3), dtype=np.uint8),
                     timestamp=float(self._i), index=self._i - 1)

    def release(self):
        pass


class FakeDetector:
    def __init__(self, lm):
        self._lm = lm

    def detect(self, frame):
        return [self._lm] if self._lm else []


class SpySink:
    def __init__(self):
        self.notifications = []
        self.recoveries = []

    def notify(self, event):
        self.notifications.append(event)

    def on_recovery(self, frame_index):
        self.recoveries.append(frame_index)


class FakePresenter:
    def __init__(self):
        self.presented = 0

    def present(self, frame, landmarks, state):
        self.presented += 1

    def should_stop(self):
        return False

    def close(self):
        pass


class RejectingValidator:
    def confirm_drowsy(self, frame, landmarks, state):
        return ContextVerdict.reject("test rejection")


class ConfirmingValidator:
    def confirm_drowsy(self, frame, landmarks, state):
        return ContextVerdict.confirm("test confirmation")


class CrashingValidator:
    def confirm_drowsy(self, frame, landmarks, state):
        raise RuntimeError("boom")


def _build(detector_lm, validator=None, fail_safe="alarm"):
    source = FakeSource(5)
    sink = SpySink()
    presenter = FakePresenter()
    detect = DetectFatigueUseCase(
        FakeDetector(detector_lm),
        FatigueThresholds(
            ear_threshold=0.25, mar_threshold=0.6,
            consecutive_frames=3, warning_ratio=1.0,
        ),
    )
    uc = MonitorDriverUseCase(
        source=source, detect=detect, sink=sink, presenter=presenter,
        context_validator=validator,
        fail_safe_on_error=fail_safe,
    )
    return uc, sink


class TestValidatorIntegration:
    def test_rejecting_validator_suppresses_alert(self):
        uc, sink = _build(_landmarks(0.05, 0.1), RejectingValidator())
        uc.run()
        assert sink.notifications == []

    def test_confirming_validator_allows_alert(self):
        uc, sink = _build(_landmarks(0.05, 0.1), ConfirmingValidator())
        uc.run()
        assert len(sink.notifications) == 1

    def test_no_validator_keeps_phase2_behavior(self):
        uc, sink = _build(_landmarks(0.05, 0.1), validator=None)
        uc.run()
        assert len(sink.notifications) == 1

    def test_crashing_validator_with_alarm_failsafe_alerts(self):
        uc, sink = _build(_landmarks(0.05, 0.1), CrashingValidator(), fail_safe="alarm")
        uc.run()
        assert len(sink.notifications) == 1

    def test_crashing_validator_with_suppress_failsafe_suppresses(self):
        uc, sink = _build(_landmarks(0.05, 0.1), CrashingValidator(), fail_safe="suppress")
        uc.run()
        assert sink.notifications == []
