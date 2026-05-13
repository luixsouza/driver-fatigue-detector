import json
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

import pytest

from driver_fatigue.interfaces.web import server as web_server


@contextmanager
def _run_server(port: int):
    httpd = web_server._QuietThreadingHTTPServer(
        ("127.0.0.1", port), web_server._Handler,
    )
    web_server._api_key = None
    web_server._started_at = time.monotonic()
    web_server._simulated_inputs.update(
        bpm=75.0, steering_noise=0.1, hours_driving=0.0, hour_of_day=12.0,
    )
    web_server._demo_runner = None
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        if web_server._demo_runner is not None:
            web_server._demo_runner.stop()
        httpd.shutdown()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post(url: str, payload: dict | None = None):
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=2)


def test_demo_start_moves_bpm_over_time():
    port = _free_port()
    with _run_server(port) as base:
        r = _post(f"{base}/api/demo/start")
        assert r.status == 202
        # script anda em 10Hz; em 1.5s o bpm ja deve ter caido do baseline 75
        time.sleep(1.5)
        with urllib.request.urlopen(f"{base}/api/inputs", timeout=2) as resp:
            data = json.loads(resp.read())
        assert data["bpm"] < 75.0, f"bpm nao moveu: {data}"


def test_demo_start_while_running_returns_409():
    port = _free_port()
    with _run_server(port) as base:
        _post(f"{base}/api/demo/start")
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(f"{base}/api/demo/start")
        assert exc.value.code == 409


def test_demo_stop_aborts_running_scenario():
    port = _free_port()
    with _run_server(port) as base:
        _post(f"{base}/api/demo/start")
        time.sleep(0.3)
        r = _post(f"{base}/api/demo/stop")
        assert r.status in (200, 202)
        # Apos stop, segundo stop retorna not_running
        r2 = _post(f"{base}/api/demo/stop")
        body = json.loads(r2.read())
        assert body["status"] == "not_running"
