from __future__ import annotations

import logging

from driver_fatigue.domain.entities import FatigueEvent

_log = logging.getLogger("driver_fatigue.alerts")


class LogSink:
    def notify(self, event: FatigueEvent) -> None:
        _log.warning(
            "FADIGA detectada | frame=%d ear=%.3f mar=%.3f",
            event.frame_index, event.state.ear, event.state.mar,
        )

    def on_recovery(self, frame_index: int) -> None:
        _log.info("Motorista recuperado | frame=%d", frame_index)
