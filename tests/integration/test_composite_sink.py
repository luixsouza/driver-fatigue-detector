from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.composite import CompositeSink


class SpySink:
    def __init__(self, raise_on: str | None = None):
        self.notified = 0
        self.recovered = 0
        self._raise = raise_on

    def notify(self, event):
        self.notified += 1
        if self._raise == "notify":
            raise RuntimeError("boom notify")

    def on_recovery(self, frame_index):
        self.recovered += 1
        if self._raise == "recovery":
            raise RuntimeError("boom recovery")


def _event():
    return FatigueEvent(
        timestamp=0.0, state=FatigueState.initial(), frame_index=0,
    )


class TestCompositeSink:
    def test_notify_fans_out(self):
        a, b = SpySink(), SpySink()
        c = CompositeSink(a, b)
        c.notify(_event())
        assert a.notified == 1 and b.notified == 1

    def test_on_recovery_fans_out(self):
        a, b = SpySink(), SpySink()
        c = CompositeSink(a, b)
        c.on_recovery(frame_index=10)
        assert a.recovered == 1 and b.recovered == 1

    def test_notify_exception_does_not_break_others(self):
        a = SpySink(raise_on="notify")
        b = SpySink()
        c = CompositeSink(a, b)
        c.notify(_event())
        assert a.notified == 1 and b.notified == 1

    def test_recovery_exception_does_not_break_others(self):
        a = SpySink(raise_on="recovery")
        b = SpySink()
        c = CompositeSink(a, b)
        c.on_recovery(frame_index=1)
        assert a.recovered == 1 and b.recovered == 1
