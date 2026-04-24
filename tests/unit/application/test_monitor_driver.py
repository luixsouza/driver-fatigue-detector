import numpy as np

from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.application.use_cases.monitor_driver import MonitorDriverUseCase
from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueState,
    Frame,
    Point,
)
from driver_fatigue.domain.value_objects import FatigueThresholds


def _eye(open_ratio):
    h = open_ratio / 2
    return (Point(0,0), Point(0.3,-h), Point(0.7,-h),
            Point(1,0), Point(0.7,h), Point(0.3,h))


def _mouth(open_ratio):
    h = open_ratio / 2
    return (Point(0,0), Point(0.15,-h), Point(0.35,-h), Point(0.5,-h),
            Point(0.65,-h), Point(0.85,-h), Point(1,0), Point(0.85,h),
            Point(0.65,h), Point(0.5,h), Point(0.35,h), Point(0.15,h))


def _landmarks(eye_open, mouth_open):
    return FaceLandmarks(
        left_eye_contour=_eye(eye_open), right_eye_contour=_eye(eye_open),
        left_iris=None, right_iris=None,
        mouth_outer=_mouth(mouth_open), mouth_inner=_mouth(mouth_open),
        face_oval=tuple(Point(float(i), 0) for i in range(36)),
    )


class FakeSource:
    def __init__(self, n: int):
        self._remaining = n
        self._i = 0
        self.released = False

    def read(self):
        if self._remaining <= 0:
            return None
        self._remaining -= 1
        self._i += 1
        img = np.zeros((2, 2, 3), dtype=np.uint8)
        return Frame(image=img, timestamp=float(self._i), index=self._i - 1)

    def release(self):
        self.released = True


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
    def __init__(self, stop_after: int = 1_000_000):
        self.presented = 0
        self._stop_after = stop_after
        self.closed = False

    def present(self, frame, landmarks, state):
        self.presented += 1

    def should_stop(self):
        return self.presented >= self._stop_after

    def close(self):
        self.closed = True


class TestMonitorDriverUseCase:
    def _build(self, n_frames, lm, stop_after=10_000):
        source = FakeSource(n_frames)
        sink = SpySink()
        presenter = FakePresenter(stop_after=stop_after)
        detect = DetectFatigueUseCase(
            FakeDetector(lm),
            FatigueThresholds(
                ear_threshold=0.25, mar_threshold=0.6,
                consecutive_frames=3, warning_ratio=0.8,
            ),
        )
        uc = MonitorDriverUseCase(
            source=source, detect=detect, sink=sink, presenter=presenter,
        )
        return uc, source, sink, presenter

    def test_stops_when_source_exhausts(self):
        uc, source, sink, presenter = self._build(n_frames=3, lm=_landmarks(0.5, 0.1))
        uc.run()
        assert presenter.presented == 3
        assert source.released is True
        assert presenter.closed is True

    def test_stops_when_presenter_requests(self):
        uc, source, sink, presenter = self._build(
            n_frames=100, lm=_landmarks(0.5, 0.1), stop_after=2,
        )
        uc.run()
        assert presenter.presented == 2

    def test_notifies_sink_on_alert(self):
        uc, source, sink, presenter = self._build(n_frames=3, lm=_landmarks(0.1, 0.1))
        uc.run()
        assert len(sink.notifications) == 1
        assert sink.notifications[0].state.severity == "alert"

    def test_notifies_recovery_after_alert(self):
        source = FakeSource(5)
        sink = SpySink()
        presenter = FakePresenter()

        class TwoPhaseDetector:
            def __init__(self):
                self.calls = 0
            def detect(self, frame):
                self.calls += 1
                if self.calls <= 3:
                    return [_landmarks(0.1, 0.1)]
                return [_landmarks(0.5, 0.1)]

        detect = DetectFatigueUseCase(
            TwoPhaseDetector(),
            FatigueThresholds(ear_threshold=0.25, mar_threshold=0.6,
                              consecutive_frames=3, warning_ratio=0.8),
        )
        MonitorDriverUseCase(
            source=source, detect=detect, sink=sink, presenter=presenter,
        ).run()
        assert len(sink.notifications) == 1
        assert len(sink.recoveries) == 1
