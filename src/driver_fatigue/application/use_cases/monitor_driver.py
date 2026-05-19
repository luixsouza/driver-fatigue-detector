from __future__ import annotations

import logging

from driver_fatigue.application.ports import (
    AlertSinkPort,
    ContextValidatorPort,
    FramePresenterPort,
    VideoSourcePort,
)
from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.domain.entities import FatigueEvent, FatigueState

_log = logging.getLogger("driver_fatigue.monitor")


class MonitorDriverUseCase:
    def __init__(
        self,
        source: VideoSourcePort,
        detect: DetectFatigueUseCase,
        sink: AlertSinkPort,
        presenter: FramePresenterPort,
        *,
        context_validator: ContextValidatorPort | None = None,
        min_validator_confidence: float = 0.6,
        fail_safe_on_error: str = "alarm",
        state_publisher = None,
        state_publish_every_frames: int = 6,
    ) -> None:
        self._source = source
        self._detect = detect
        self._sink = sink
        self._presenter = presenter
        self._validator = context_validator
        self._min_confidence = min_validator_confidence
        self._fail_safe_on_error = fail_safe_on_error
        self._state_publisher = state_publisher
        self._state_publish_every = max(1, state_publish_every_frames)

    def run(self) -> None:
        state = FatigueState.initial()
        try:
            while not self._presenter.should_stop():
                frame = self._source.read()
                if frame is None:
                    break
                new_state, faces = self._detect.execute(frame, state)
                self._maybe_notify(
                    previous=state,
                    current=new_state,
                    frame=frame,
                    faces=faces,
                )
                if (
                    self._state_publisher is not None
                    and frame.index % self._state_publish_every == 0
                ):
                    try:
                        self._state_publisher(frame, new_state)
                    except Exception as exc:  # publisher é best-effort
                        _log.debug("state publisher falhou: %s", exc)
                self._presenter.present(frame, faces, new_state)
                state = new_state
        finally:
            self._source.release()
            self._presenter.close()

    def _maybe_notify(
        self,
        *,
        previous: FatigueState,
        current: FatigueState,
        frame,
        faces,
    ) -> None:
        entered_alert = previous.severity != "alert" and current.severity == "alert"
        left_alert = previous.severity == "alert" and current.severity == "normal"
        if entered_alert:
            if (
                self._validator is not None
                and faces
                and not self._is_confirmed(frame, faces[0], current)
            ):
                _log.info("ctx_suppressed: alarme inibido por context validator")
                return
            self._sink.notify(FatigueEvent(
                timestamp=frame.timestamp if frame is not None else float(current.consecutive_frames),
                state=current,
                frame_index=frame.index if frame is not None else 0,
            ))
        elif left_alert:
            self._sink.on_recovery(frame.index if frame is not None else 0)

    def _is_confirmed(self, frame, face, state: FatigueState) -> bool:
        try:
            verdict = self._validator.confirm_drowsy(frame, face, state)
        except Exception as exc:
            _log.warning("context validator falhou (%s): fail_safe=%s", exc, self._fail_safe_on_error)
            return self._fail_safe_on_error != "suppress"
        if not verdict.drowsy:
            return False
        return verdict.confidence >= self._min_confidence
