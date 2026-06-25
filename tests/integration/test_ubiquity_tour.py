"""Testa o Tour Ubiquo: endpoints, sinks espioes e o runner ponta-a-ponta."""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

from driver_fatigue.interfaces.web import server as web_server
from driver_fatigue.interfaces.web import ubiquity_tour as tour


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _run_server(port: int):
    httpd = web_server._QuietThreadingHTTPServer(
        ("127.0.0.1", port), web_server._Handler,
    )
    web_server._api_key = None
    web_server._started_at = time.monotonic()
    web_server._server_host = "127.0.0.1"
    web_server._server_port = port
    web_server._active_runner = None
    web_server._tour_runner = None
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        if web_server._tour_runner is not None:
            web_server._tour_runner.stop()
        httpd.shutdown()


def _post(url: str, payload: dict | None = None, headers: dict | None = None):
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    return urllib.request.urlopen(req, timeout=3)


# --------------------------------------------------------------------------- #
# Sinks espioes / helpers puros
# --------------------------------------------------------------------------- #
def test_composite_isola_falha_do_mqtt():
    from driver_fatigue.infrastructure.alert_sinks.composite import CompositeSink

    log = tour._SpyAlertSink("Log", "stdout")
    mqtt = tour._SpyAlertSink("MQTT", "rede", fail=True)
    http = tour._SpyAlertSink("HTTP", "rede")
    CompositeSink(log, mqtt, http).notify(tour._synthetic_alert_event())

    assert log.delivered is True
    assert http.delivered is True          # falha do mqtt nao derrubou os outros
    assert mqtt.delivered is False
    assert mqtt.to_report()["isolated"] is True


def test_jsonl_spy_grava_arquivo_real(tmp_path: Path):
    path = tmp_path / "ev.jsonl"
    spy = tour._JsonlSpy(path)
    spy.notify(tour._synthetic_alert_event())
    assert path.exists()
    rec = json.loads(path.read_text(encoding="utf-8").strip())
    assert rec["event"] == "fatigue_alert"


def test_scan_nao_acha_imagem_em_evento_real(tmp_path: Path):
    path = tmp_path / "ev.jsonl"
    tour._JsonlSpy(path).notify(tour._synthetic_alert_event())
    records = tour._tail_jsonl(path)
    assert records
    assert tour._scan_for_image_fields(records) == []   # zero imagem → privacidade


def test_scan_detecta_campo_de_imagem():
    assert tour._scan_for_image_fields([{"frame_jpeg": "..."}]) == ["frame_jpeg"]


# --------------------------------------------------------------------------- #
# Endpoint de seguranca
# --------------------------------------------------------------------------- #
def test_secure_echo_401_sem_chave():
    port = _free_port()
    with _run_server(port) as base:
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(f"{base}/api/demo/secure-echo", {"probe": "x"})
        assert exc.value.code == 401


def test_secure_echo_200_com_chave():
    port = _free_port()
    with _run_server(port) as base:
        r = _post(f"{base}/api/demo/secure-echo", {"probe": "x"},
                  headers={"X-Demo-Key": tour.DEMO_SECURE_KEY})
        assert r.status == 200
        assert json.loads(r.read())["authenticated"] is True


# --------------------------------------------------------------------------- #
# Endpoint do tour (singleton)
# --------------------------------------------------------------------------- #
def test_tour_start_retorna_202_e_segundo_da_409():
    port = _free_port()
    with _run_server(port) as base:
        r = _post(f"{base}/api/demo/tour/start")
        assert r.status == 202
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(f"{base}/api/demo/tour/start")
        assert exc.value.code == 409


# --------------------------------------------------------------------------- #
# Runner ponta-a-ponta (com servidor real pro loopback de seguranca/distrib.)
# --------------------------------------------------------------------------- #
def test_runner_emite_5_passos_e_lifecycle(tmp_path: Path):
    port = _free_port()
    collected: list[dict] = []
    with _run_server(port):
        runner = tour.UbiquityTourRunner(
            broadcast=collected.append,
            host="127.0.0.1",
            port=port,
            api_key=None,
            fault_injector=None,            # sem detector embutido no teste
            topology_probe=lambda: {"detector_embedded": False},
            demo_dir=tmp_path,
            step_pause=0.05,
        )
        runner.start()
        deadline = time.monotonic() + 10
        while runner.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not runner.is_alive(), "tour nao terminou a tempo"

    lifecycles = [e for e in collected if e.get("kind") == "lifecycle"]
    assert lifecycles[0]["status"] == "started"
    assert lifecycles[-1]["status"] == "finished"

    done = {e["step"]: e for e in collected
            if e.get("kind") == "step" and e.get("status") == "done"}
    for step in tour.STEP_ORDER:
        assert step in done, f"passo {step} nao concluiu"

    # seguranca: sem chave bloqueou, com chave aceitou
    assert done["security"]["data"]["passed"] is True
    # distribuicao: POST /api/events real respondeu 202
    assert done["distribution"]["data"]["http_status"] == 202
    # heterogeneidade: 4 entregues, 1 isolado
    assert done["heterogeneity"]["data"]["delivered"] == 4
    assert done["heterogeneity"]["data"]["isolated"] == 1
    # privacidade: nenhum campo de imagem
    assert done["privacy"]["data"]["no_image"] is True
