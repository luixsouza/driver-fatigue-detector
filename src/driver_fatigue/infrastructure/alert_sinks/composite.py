from __future__ import annotations

import logging

from driver_fatigue.application.ports import AlertSinkPort
from driver_fatigue.domain.entities import FatigueEvent

_log = logging.getLogger("driver_fatigue.alerts")


class CompositeSink:
    """Fan-out de eventos para múltiplos sinks com isolamento de falhas."""

    def __init__(self, *sinks: AlertSinkPort) -> None:
        self._sinks = sinks

    def notify(self, event: FatigueEvent) -> None:
        for s in self._sinks:
            try:
                s.notify(event)
            except Exception:
                _log.exception("sink %s falhou em notify", type(s).__name__)

    def on_recovery(self, frame_index: int) -> None:
        for s in self._sinks:
            try:
                s.on_recovery(frame_index)
            except Exception:
                _log.exception("sink %s falhou em on_recovery", type(s).__name__)
