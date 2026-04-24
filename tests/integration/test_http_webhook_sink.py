import httpx
import pytest
import respx

from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.http_webhook import HttpWebhookSink


def _alert_event():
    return FatigueEvent(
        timestamp=1.5,
        state=FatigueState(
            ear=0.18, mar=0.52, consecutive_frames=20,
            is_fatigued=True, is_yawning=False, severity="alert",
        ),
        frame_index=100,
    )


class TestHttpWebhookSink:
    @respx.mock
    def test_notify_posts_json_payload(self):
        route = respx.post("https://hook.example/events").mock(
            return_value=httpx.Response(200),
        )
        sink = HttpWebhookSink(url="https://hook.example/events")
        sink.notify(_alert_event())
        assert route.called
        req = route.calls.last.request
        import json
        payload = json.loads(req.content)
        assert payload["event"] == "fatigue_alert"
        assert payload["frame_index"] == 100
        assert payload["severity"] == "alert"
        assert payload["ear"] == pytest.approx(0.18)
        assert payload["mar"] == pytest.approx(0.52)

    @respx.mock
    def test_on_recovery_posts_recovery_event(self):
        route = respx.post("https://hook.example/events").mock(
            return_value=httpx.Response(204),
        )
        sink = HttpWebhookSink(url="https://hook.example/events")
        sink.on_recovery(frame_index=200)
        assert route.called
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["event"] == "fatigue_recovery"
        assert payload["frame_index"] == 200

    @respx.mock
    def test_bearer_token_sent_in_authorization_header(self):
        route = respx.post("https://hook.example/events").mock(
            return_value=httpx.Response(200),
        )
        sink = HttpWebhookSink(
            url="https://hook.example/events",
            bearer_token="secret-123",
        )
        sink.notify(_alert_event())
        assert route.called
        headers = route.calls.last.request.headers
        assert headers.get("authorization") == "Bearer secret-123"

    @respx.mock
    def test_timeout_is_swallowed(self):
        respx.post("https://hook.example/events").mock(
            side_effect=httpx.TimeoutException("boom"),
        )
        sink = HttpWebhookSink(url="https://hook.example/events", timeout_seconds=0.1)
        sink.notify(_alert_event())

    @respx.mock
    def test_5xx_is_swallowed(self):
        respx.post("https://hook.example/events").mock(
            return_value=httpx.Response(500),
        )
        sink = HttpWebhookSink(url="https://hook.example/events")
        sink.notify(_alert_event())
