"""Confirma que publish_state inclui fatigue_index/severity/explain
no payload SSE quando o evaluator esta plugado."""
import time

from driver_fatigue.domain.entities import FatigueState, Frame
from driver_fatigue.domain.fatigue_index import FatigueIndex
from driver_fatigue.interfaces.web import server as web_server


class _StubEvaluator:
    def compute(self, inputs):
        return FatigueIndex(
            value=72.0, severity="alert",
            top_contributors=("R4",), explain="BPM baixo + olhos parciais",
            critical=False,
        )


def test_publish_state_includes_index_fields():
    captured: list[dict] = []
    original = web_server._broadcast
    web_server._broadcast = lambda ev: captured.append(ev)
    try:
        sink = web_server._InProcessAlertSink(evaluator=_StubEvaluator())
        frame = Frame(image=None, timestamp=time.time(), index=42)  # type: ignore[arg-type]
        state = FatigueState.initial()
        sink.publish_state(frame, state)
    finally:
        web_server._broadcast = original

    assert len(captured) == 1
    ev = captured[0]
    assert ev["event"] == "state"
    assert ev["fatigue_index"] == 72.0
    assert ev["index_severity"] == "alert"
    assert ev["explain"] == "BPM baixo + olhos parciais"
    assert ev["top_contributors"] == ["R4"]
    assert ev["critical"] is False
