"""Smoke E2E: levanta o server, faz POST /api/inputs com BPM baixo e
confirma que o proximo evento 'state' tem fatigue_index reagindo.

Nao depende de webcam — mockamos a thread do detector pra publicar
estados sintéticos a 5Hz."""
import json
import socket
import threading
import time
import urllib.request
from contextlib import contextmanager

import pytest

skfuzzy = pytest.importorskip("skfuzzy")

from driver_fatigue.domain.entities import Frame, FatigueState
from driver_fatigue.interfaces.web import server as web_server


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _running_dashboard(port: int):
    """Sobe http server + thread que faz publish_state a 5Hz."""
    from driver_fatigue.bootstrap import _build_index_evaluator
    from driver_fatigue.config.settings import AppSettings
    web_server._api_key = None
    web_server._started_at = time.monotonic()
    web_server._simulated_inputs.update(
        bpm=75.0, steering_noise=0.1, hours_driving=0.0, hour_of_day=12.0,
    )
    settings = AppSettings()
    evaluator = _build_index_evaluator(settings)
    sink = web_server._InProcessAlertSink(evaluator=evaluator)

    httpd = web_server._QuietThreadingHTTPServer(
        ("127.0.0.1", port), web_server._Handler,
    )
    stop = threading.Event()

    healthy_state = FatigueState(
        ear=0.30, mar=0.20, consecutive_frames=0,
        is_fatigued=False, is_yawning=False, severity="normal",
    )

    def _publisher():
        i = 0
        while not stop.is_set():
            frame = Frame(image=None, timestamp=time.time(), index=i)  # type: ignore[arg-type]
            sink.publish_state(frame, healthy_state)
            i += 1
            stop.wait(0.2)

    server_t = threading.Thread(target=httpd.serve_forever, daemon=True)
    pub_t = threading.Thread(target=_publisher, daemon=True)
    server_t.start(); pub_t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        stop.set()
        httpd.shutdown()


def _read_one_state(base: str, timeout: float = 3.0) -> dict:
    """Le um unico evento 'state' do SSE."""
    req = urllib.request.Request(f"{base}/api/stream")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline:
            chunk = r.read1(2048)
            if not chunk:
                continue
            buf += chunk
            while b"\n\n" in buf:
                event, _, buf = buf.partition(b"\n\n")
                line = event.decode("utf-8")
                for ln in line.splitlines():
                    if ln.startswith("data: "):
                        payload = json.loads(ln[6:])
                        if payload.get("event") == "state":
                            return payload
        raise TimeoutError("no state event")


def test_lowering_bpm_raises_fatigue_index():
    port = _free_port()
    with _running_dashboard(port) as base:
        time.sleep(0.4)
        baseline = _read_one_state(base)
        baseline_idx = baseline["fatigue_index"]

        # baixa BPM pra 45 e simula 7h de direcao em madrugada
        body = json.dumps({
            "bpm": 45.0, "hours_driving": 7.0, "hour_of_day": 3.5,
            "steering_noise": 0.6,
        }).encode()
        req = urllib.request.Request(
            f"{base}/api/inputs", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=2)

        time.sleep(0.6)
        worse = _read_one_state(base)
        assert worse["fatigue_index"] > baseline_idx + 5, (
            f"indice nao subiu: {baseline_idx:.1f} -> {worse['fatigue_index']:.1f}"
        )
