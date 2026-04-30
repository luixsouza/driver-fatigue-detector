"""Testa o servidor web com X-API-Key e o endpoint /health."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from driver_fatigue.interfaces.web import server as web_server


def _free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def web_with_key():
    """Sobe o servidor numa porta livre, com api_key, em thread."""
    port = _free_port()
    web_server._api_key = "secret-key"
    web_server._started_at = time.monotonic()
    web_server._last_event = None
    web_server._last_event_at = 0.0
    web_server._last_jpeg = None
    web_server._last_jpeg_at = 0.0
    httpd = ThreadingHTTPServer(("127.0.0.1", port), web_server._Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        web_server._api_key = None


@pytest.fixture
def web_without_key():
    port = _free_port()
    web_server._api_key = None
    web_server._started_at = time.monotonic()
    web_server._last_event = None
    web_server._last_event_at = 0.0
    web_server._last_jpeg = None
    web_server._last_jpeg_at = 0.0
    httpd = ThreadingHTTPServer(("127.0.0.1", port), web_server._Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()


def _post(port: int, path: str, body: bytes, headers: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body, method="POST", headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def _get(port: int, path: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        return exc.code, json.loads(body) if body else {}


class TestApiKeyEnforcement:
    def test_post_events_rejected_without_key(self, web_with_key):
        status, _ = _post(
            web_with_key, "/api/events",
            b'{"event":"x"}', {"Content-Type": "application/json"},
        )
        assert status == 401

    def test_post_events_rejected_with_wrong_key(self, web_with_key):
        status, _ = _post(
            web_with_key, "/api/events", b'{"event":"x"}',
            {"Content-Type": "application/json", "X-API-Key": "wrong"},
        )
        assert status == 401

    def test_post_events_accepted_with_correct_key(self, web_with_key):
        status, body = _post(
            web_with_key, "/api/events", b'{"event":"x","severity":"alert"}',
            {"Content-Type": "application/json", "X-API-Key": "secret-key"},
        )
        assert status == 202
        assert body == {"status": "accepted"}

    def test_post_video_rejected_without_key(self, web_with_key):
        status, _ = _post(
            web_with_key, "/api/video/push",
            b"\xff\xd8\xff\xd9", {"Content-Type": "image/jpeg"},
        )
        assert status == 401

    def test_post_video_accepted_with_correct_key(self, web_with_key):
        status, _ = _post(
            web_with_key, "/api/video/push",
            b"\xff\xd8\xff\xd9",
            {"Content-Type": "image/jpeg", "X-API-Key": "secret-key"},
        )
        assert status == 202

    def test_get_health_does_not_require_key(self, web_with_key):
        status, body = _get(web_with_key, "/api/health")
        assert status in (200, 503)
        assert body["auth_required"] is True


class TestApiKeyDisabled:
    def test_post_events_works_without_key_when_unset(self, web_without_key):
        status, body = _post(
            web_without_key, "/api/events",
            b'{"event":"x"}', {"Content-Type": "application/json"},
        )
        assert status == 202
        assert body == {"status": "accepted"}

    def test_health_reports_auth_optional(self, web_without_key):
        status, body = _get(web_without_key, "/api/health")
        assert status in (200, 503)
        assert body["auth_required"] is False


class TestHealthEndpoint:
    def test_health_path_alias(self, web_without_key):
        status_a, body_a = _get(web_without_key, "/api/health")
        status_b, body_b = _get(web_without_key, "/health")
        assert status_a == status_b
        assert body_a.keys() == body_b.keys()

    def test_health_reports_no_signal_initially(self, web_without_key):
        status, body = _get(web_without_key, "/api/health")
        assert status == 503
        assert body["ok"] is False
        assert body["video_age_seconds"] is None
        assert body["event_age_seconds"] is None
        assert body["last_severity"] is None

    def test_health_reports_ok_after_event(self, web_without_key):
        _post(
            web_without_key, "/api/events",
            b'{"event":"state","severity":"normal"}',
            {"Content-Type": "application/json"},
        )
        _post(
            web_without_key, "/api/video/push",
            b"\xff\xd8\xff\xd9", {"Content-Type": "image/jpeg"},
        )
        status, body = _get(web_without_key, "/api/health")
        assert status == 200
        assert body["ok"] is True
        assert body["last_severity"] == "normal"
        assert body["uptime_seconds"] is not None and body["uptime_seconds"] >= 0
