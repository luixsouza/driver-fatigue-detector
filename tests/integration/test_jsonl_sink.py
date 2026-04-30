import json

from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.domain.value_objects import FrameQuality, PersonalBaseline
from driver_fatigue.infrastructure.alert_sinks.jsonl import JsonlEventSink


def _make_event() -> FatigueEvent:
    return FatigueEvent(
        timestamp=12.5,
        state=FatigueState(
            ear=0.18,
            mar=0.42,
            consecutive_frames=22,
            is_fatigued=True,
            is_yawning=False,
            severity="alert",
            recovery_frames=0,
            last_alert_timestamp=12.5,
            baseline=PersonalBaseline(
                ear_rest=0.31, mar_rest=0.18,
                ear_std=0.02, mar_std=0.03, sample_count=60,
            ),
            quality=FrameQuality.trusted(),
        ),
        frame_index=10523,
    )


class TestJsonlEventSink:
    def test_notify_writes_alert_line(self, tmp_path):
        target = tmp_path / "events.jsonl"
        sink = JsonlEventSink(path=target)
        sink.notify(_make_event())

        lines = target.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event"] == "fatigue_alert"
        assert record["frame_index"] == 10523
        assert record["ear"] == 0.18
        assert record["mar"] == 0.42
        assert record["severity"] == "alert"
        assert record["calibrated"] is True
        assert record["baseline_ear"] == 0.31
        assert record["quality_ok"] is True

    def test_on_recovery_appends_recovery_line(self, tmp_path):
        target = tmp_path / "events.jsonl"
        sink = JsonlEventSink(path=target)
        sink.notify(_make_event())
        sink.on_recovery(frame_index=10760)

        lines = target.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        recovery = json.loads(lines[1])
        assert recovery["event"] == "fatigue_recovery"
        assert recovery["frame_index"] == 10760

    def test_creates_parent_directory(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "events.jsonl"
        sink = JsonlEventSink(path=target)
        sink.notify(_make_event())
        assert target.exists()

    def test_append_only_across_instances(self, tmp_path):
        target = tmp_path / "events.jsonl"
        JsonlEventSink(path=target).notify(_make_event())
        JsonlEventSink(path=target).notify(_make_event())
        lines = target.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
