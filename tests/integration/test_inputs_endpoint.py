import json
import threading
import time
import urllib.request
from contextlib import contextmanager

import pytest

from driver_fatigue.interfaces.web import server as web_server


@contextmanager
def _run_server(port: int, api_key: str | None = None):
    httpd = web_server._QuietThreadingHTTPServer(
        ("127.0.0.1", port), web_server._Handler,
    )
    web_server._api_key = api_key
    web_server._started_at = time.monotonic()
    # reset state
    web_server._simulated_inputs.update(
        bpm=75.0, steering_noise=0.1, hours_driving=0.0, hour_of_day=12.0,
    )
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


def _free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_post_inputs_updates_snapshot():
    port = _free_port()
    with _run_server(port) as base:
        body = json.dumps({"bpm": 60.0, "steering_noise": 0.5}).encode()
        req = urllib.request.Request(
            f"{base}/api/inputs", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            assert r.status == 202

        with urllib.request.urlopen(f"{base}/api/inputs", timeout=2) as r:
            data = json.loads(r.read())
        assert data["bpm"] == 60.0
        assert data["steering_noise"] == 0.5
        assert data["hours_driving"] == 0.0  # preserva ausente


def test_post_inputs_clamps_out_of_range():
    port = _free_port()
    with _run_server(port) as base:
        body = json.dumps({"bpm": 999.0, "steering_noise": -0.5}).encode()
        req = urllib.request.Request(
            f"{base}/api/inputs", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=2)
        with urllib.request.urlopen(f"{base}/api/inputs", timeout=2) as r:
            data = json.loads(r.read())
        assert data["bpm"] == 120.0
        assert data["steering_noise"] == 0.0


def test_post_inputs_requires_auth_when_configured():
    port = _free_port()
    with _run_server(port, api_key="secret") as base:
        body = json.dumps({"bpm": 60.0}).encode()
        req = urllib.request.Request(
            f"{base}/api/inputs", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=2)
        assert exc.value.code == 401
