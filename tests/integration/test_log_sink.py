import logging

from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.log import LogSink


class TestLogSink:
    def test_notify_emits_warning_record(self, caplog):
        sink = LogSink()
        event = FatigueEvent(
            timestamp=1.5,
            state=FatigueState(
                ear=0.18, mar=0.2, consecutive_frames=20,
                is_fatigued=True, is_yawning=False, severity="alert",
            ),
            frame_index=100,
        )
        with caplog.at_level(logging.WARNING):
            sink.notify(event)
        assert any("FADIGA" in r.message.upper() for r in caplog.records)

    def test_on_recovery_emits_info(self, caplog):
        sink = LogSink()
        with caplog.at_level(logging.INFO):
            sink.on_recovery(frame_index=200)
        assert any("recup" in r.message.lower() or "recovery" in r.message.lower()
                   for r in caplog.records)
