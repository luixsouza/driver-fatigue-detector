from __future__ import annotations

from driver_fatigue.application.ports import (
    AlertSinkPort,
    FramePresenterPort,
    VideoSourcePort,
)
from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.domain.entities import FatigueEvent, FatigueState


class MonitorDriverUseCase:
    def __init__(
        self,
        source: VideoSourcePort,
        detect: DetectFatigueUseCase,
        sink: AlertSinkPort,
        presenter: FramePresenterPort,
    ) -> None:
        self._source = source
        self._detect = detect
        self._sink = sink
        self._presenter = presenter

    def run(self) -> None:
        state = FatigueState.initial()
        try:
            while not self._presenter.should_stop():
                frame = self._source.read()
                if frame is None:
                    break
                new_state, faces = self._detect.execute(frame, state)

                self._maybe_notify(previous=state, current=new_state, frame_index=frame.index)

                self._presenter.present(frame, faces, new_state)
                state = new_state
        finally:
            self._source.release()
            self._presenter.close()

    def _maybe_notify(
        self,
        previous: FatigueState,
        current: FatigueState,
        frame_index: int,
    ) -> None:
        entered_alert = previous.severity != "alert" and current.severity == "alert"
        left_alert = previous.severity == "alert" and current.severity == "normal"
        if entered_alert:
            self._sink.notify(FatigueEvent(
                timestamp=float(frame_index),
                state=current,
                frame_index=frame_index,
            ))
        elif left_alert:
            self._sink.on_recovery(frame_index)
