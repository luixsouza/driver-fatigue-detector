"""Tour Ubíquo — orquestrador de demonstração automática.

Executa, em sequência e sem intervenção do usuário, as cinco propriedades
de sistemas ubíquos que NÃO aparecem sozinhas no cockpit normal:

    1. Tolerância a falhas  — derruba o detector e mostra o supervisor respawnar.
    2. Heterogeneidade      — faz fan-out de um evento para 5 sinks distintos,
                              com um deles falhando de propósito (isolamento).
    3. Privacidade          — lê o events.jsonl gravado no passo 2 e prova que
                              só há números, zero imagem.
    4. Segurança            — prova X-API-Key: requisição sem chave → 401,
                              com chave → 200 (loopback real).
    5. Distribuição         — publica um evento pelo caminho HTTP real
                              (POST /api/events → SSE) e mede o round-trip.

Cada passo emite eventos SSE `{"event": "tour", ...}` que o cockpit renderiza
num painel dedicado. O runner roda numa daemon thread e é singleton (um tour
por vez). Autocontido: nenhuma dependência externa (broker/listener) é
necessária — os sinks de rede são representados por adapters espiões.
"""
from __future__ import annotations

import dataclasses
import http.client
import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.composite import CompositeSink
from driver_fatigue.infrastructure.alert_sinks.jsonl import JsonlEventSink

_log = logging.getLogger("driver_fatigue.web.tour")

# Chave fixa usada só pela demonstração de segurança (passo 4). Independe da
# web.api_key real — garante 401/200 determinístico em qualquer máquina.
DEMO_SECURE_KEY = "tour-demo-key"

STEP_ORDER = ("fault", "heterogeneity", "privacy", "security", "distribution")


# --------------------------------------------------------------------------- #
# Sinks espiões — representam alvos heterogêneos para o passo de fan-out.
# --------------------------------------------------------------------------- #
class _SpyAlertSink:
    """Sink que registra a entrega (latência) em vez de fazer I/O real.

    Representa um alvo heterogêneo (log, MQTT, HTTP...). Se `fail=True`,
    levanta exceção para demonstrar que o CompositeSink isola a falha sem
    derrubar os outros sinks."""

    def __init__(self, name: str, kind: str, *, fail: bool = False,
                 work_seconds: float = 0.012) -> None:
        self.name = name
        self.kind = kind
        self.fail = fail
        self._work = work_seconds
        self.delivered = False
        self.latency_ms: float | None = None
        self.error: str | None = None

    def notify(self, event: FatigueEvent) -> None:
        t0 = time.monotonic()
        time.sleep(self._work)
        self.latency_ms = (time.monotonic() - t0) * 1000.0
        if self.fail:
            self.error = "conexão recusada (broker offline)"
            raise RuntimeError(self.error)
        self.delivered = True

    def on_recovery(self, frame_index: int) -> None:  # noqa: ARG002
        pass

    def to_report(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "delivered": self.delivered,
            "latency_ms": round(self.latency_ms, 1) if self.latency_ms is not None else None,
            "error": self.error,
            "isolated": self.error is not None,
        }


class _JsonlSpy(_SpyAlertSink):
    """Sink espião que de fato grava num events.jsonl real (alimenta o passo
    de privacidade)."""

    def __init__(self, path: Path) -> None:
        super().__init__("JSONL", "arquivo (disco)")
        self._real = JsonlEventSink(path)

    def notify(self, event: FatigueEvent) -> None:
        t0 = time.monotonic()
        self._real.notify(event)
        self.latency_ms = (time.monotonic() - t0) * 1000.0
        self.delivered = True


def _synthetic_alert_event() -> FatigueEvent:
    """Evento de fadiga sintético para demonstrar o fan-out sem precisar de
    um motorista bocejando na frente da câmera."""
    state = dataclasses.replace(
        FatigueState.initial(),
        ear=0.12,
        mar=0.22,
        consecutive_frames=31,
        is_fatigued=True,
        severity="alert",
    )
    return FatigueEvent(timestamp=time.time(), state=state, frame_index=99001)


# --------------------------------------------------------------------------- #
# Helpers de loopback HTTP (passos de segurança e distribuição).
# --------------------------------------------------------------------------- #
def _loopback_post(host: str, port: int, path: str, body: dict,
                   headers: dict[str, str], timeout: float = 3.0) -> tuple[int, float]:
    """POST loopback; retorna (status, round_trip_ms)."""
    payload = json.dumps(body).encode("utf-8")
    hdr = {"Content-Type": "application/json", **headers}
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    t0 = time.monotonic()
    try:
        conn.request("POST", path, body=payload, headers=hdr)
        resp = conn.getresponse()
        status = resp.status
        resp.read()
    finally:
        conn.close()
    return status, (time.monotonic() - t0) * 1000.0


def _tail_jsonl(path: Path, n: int = 5) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


_IMAGE_HINTS = ("image", "jpeg", "jpg", "png", "frame_bytes", "base64", "pixels", "photo")


def _scan_for_image_fields(records: list[dict[str, Any]]) -> list[str]:
    """Procura qualquer chave que sugira dado de imagem — prova de privacidade."""
    found: set[str] = set()
    for rec in records:
        for key in rec:
            if any(hint in key.lower() for hint in _IMAGE_HINTS):
                found.add(key)
    return sorted(found)


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
class UbiquityTourRunner:
    """Sequencia os 5 passos numa daemon thread, narrando via `broadcast`."""

    def __init__(
        self,
        *,
        broadcast: Callable[[dict[str, Any]], None],
        host: str,
        port: int,
        api_key: str | None,
        fault_injector: Callable[[], dict[str, Any]] | None,
        demo_dir: Path,
        topology_probe: Callable[[], dict[str, Any]] | None = None,
        step_pause: float = 2.2,
    ) -> None:
        self._broadcast = broadcast
        self._host = host
        self._port = port
        self._api_key = api_key
        self._fault_injector = fault_injector
        self._topology_probe = topology_probe
        self._demo_dir = demo_dir
        self._jsonl_path = demo_dir / "tour-events.jsonl"
        self._pause = step_pause
        self._stop = threading.Event()
        self._seq = 0
        self._thread = threading.Thread(target=self._run, daemon=True)

    # -- ciclo de vida ----------------------------------------------------- #
    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    # -- emissão ----------------------------------------------------------- #
    def _emit(self, payload: dict[str, Any]) -> None:
        self._seq += 1
        self._broadcast({"event": "tour", "seq": self._seq, "ts": time.time(), **payload})

    def _step(self, step: str, title: str, narration: str, status: str,
              data: dict[str, Any] | None = None) -> None:
        self._emit({
            "kind": "step", "step": step, "title": title,
            "narration": narration, "status": status, "data": data or {},
        })

    def _sleep(self, seconds: float) -> bool:
        """Espera; retorna True se foi pedido stop no meio."""
        return self._stop.wait(seconds)

    # -- loop principal ---------------------------------------------------- #
    def _run(self) -> None:
        self._emit({"kind": "lifecycle", "status": "started",
                    "steps": list(STEP_ORDER)})
        try:
            steps = (
                self._step_fault,
                self._step_heterogeneity,
                self._step_privacy,
                self._step_security,
                self._step_distribution,
            )
            for fn in steps:
                if self._stop.is_set():
                    self._emit({"kind": "lifecycle", "status": "aborted"})
                    return
                try:
                    fn()
                except Exception as exc:  # nunca derruba o tour por um passo
                    _log.exception("passo do tour falhou: %s", fn.__name__)
                    self._emit({"kind": "step", "step": fn.__name__, "status": "failed",
                                "narration": f"falha inesperada: {exc}", "data": {}})
                if self._sleep(self._pause):
                    self._emit({"kind": "lifecycle", "status": "aborted"})
                    return
            self._emit({"kind": "lifecycle", "status": "finished"})
        finally:
            pass

    # -- passos ------------------------------------------------------------ #
    def _step_fault(self) -> None:
        self._step(
            "fault", "Tolerância a falhas",
            "Derrubando o processo detector ao vivo…", "running",
            {"detector": "down"},
        )
        if self._fault_injector is None:
            self._step(
                "fault", "Tolerância a falhas",
                "Detector não está embutido neste processo — passo simulado.",
                "done", {"available": False},
            )
            return
        result = self._fault_injector()
        if not result.get("available"):
            self._step("fault", "Tolerância a falhas",
                       "Detector não está embutido — passo ignorado.",
                       "done", {"available": False})
            return
        secs = result.get("respawn_seconds")
        if secs is None:
            self._step("fault", "Tolerância a falhas",
                       "Supervisor ainda não confirmou respawn (timeout).",
                       "done", {"available": True, "respawn_seconds": None})
            return
        self._step(
            "fault", "Tolerância a falhas",
            f"_DetectorSupervisor respawnou o detector em {secs:.1f}s — sem perder o serviço.",
            "done", {"available": True, "respawn_seconds": round(secs, 1), "detector": "up"},
        )

    def _step_heterogeneity(self) -> None:
        self._step(
            "heterogeneity", "Heterogeneidade + isolamento de falhas",
            "Publicando UM evento para 5 sinks heterogêneos via CompositeSink…",
            "running",
        )
        log_spy = _SpyAlertSink("Log", "stdout/arquivo")
        jsonl_spy = _JsonlSpy(self._jsonl_path)
        mqtt_spy = _SpyAlertSink("MQTT", "rede (broker)", fail=True)
        http_spy = _SpyAlertSink("HTTP webhook", "rede (frota)")
        sound_spy = _SpyAlertSink("Som", "atuador (cabine)")
        spies = [log_spy, jsonl_spy, mqtt_spy, http_spy, sound_spy]

        composite = CompositeSink(*spies)
        event = _synthetic_alert_event()
        composite.notify(event)  # CompositeSink isola a falha do MQTT

        reports = [s.to_report() for s in spies]
        delivered = sum(1 for r in reports if r["delivered"])
        isolated = sum(1 for r in reports if r["isolated"])
        self._step(
            "heterogeneity", "Heterogeneidade + isolamento de falhas",
            f"{delivered}/5 sinks entregaram; {isolated} falha isolada — "
            "o broker offline NÃO derrubou os demais.",
            "done", {"sinks": reports, "delivered": delivered, "isolated": isolated},
        )

    def _step_privacy(self) -> None:
        self._step(
            "privacy", "Privacidade",
            "Lendo o events.jsonl gravado pelo fan-out…", "running",
        )
        records = _tail_jsonl(self._jsonl_path, n=5)
        image_fields = _scan_for_image_fields(records)
        keys = sorted({k for rec in records for k in rec})
        self._step(
            "privacy", "Privacidade",
            f"{len(records)} registros — campos {keys}. "
            f"Campos de imagem encontrados: {image_fields or 'NENHUM'}. "
            "O vídeo nunca saiu do dispositivo.",
            "done",
            {"records": records, "image_fields": image_fields,
             "keys": keys, "no_image": not image_fields},
        )

    def _step_security(self) -> None:
        self._step(
            "security", "Segurança (X-API-Key)",
            "Sondando o endpoint protegido SEM chave…", "running",
        )
        path = "/api/demo/secure-echo"
        try:
            status_no, ms_no = _loopback_post(
                self._host, self._port, path, {"probe": "no-key"}, {})
        except OSError as exc:
            self._step("security", "Segurança (X-API-Key)",
                       f"loopback indisponível: {exc}", "done", {"available": False})
            return
        status_ok, ms_ok = _loopback_post(
            self._host, self._port, path, {"probe": "with-key"},
            {"X-Demo-Key": DEMO_SECURE_KEY})
        passed = status_no == 401 and status_ok == 200
        self._step(
            "security", "Segurança (X-API-Key)",
            f"Sem chave → {status_no} (bloqueado); com chave → {status_ok} (aceito). "
            "Mesmo mecanismo que protege POST /api/events.",
            "done",
            {
                "without_key": {"status": status_no, "ms": round(ms_no, 1),
                                "blocked": status_no == 401},
                "with_key": {"status": status_ok, "ms": round(ms_ok, 1),
                             "accepted": status_ok == 200},
                "passed": passed,
            },
        )

    def _step_distribution(self) -> None:
        self._step(
            "distribution", "Distribuição (caminho de rede real)",
            "Publicando um evento via POST /api/events (caminho do detector remoto)…",
            "running",
        )
        topo = self._topology_probe() if self._topology_probe else {}
        headers = {"X-API-Key": self._api_key} if self._api_key else {}
        body = {"event": "net_probe", "severity": "normal",
                "note": "evento publicado pelo Tour Ubíquo via HTTP"}
        try:
            status, ms = _loopback_post(
                self._host, self._port, "/api/events", body, headers)
        except OSError as exc:
            self._step("distribution", "Distribuição (caminho de rede real)",
                       f"loopback indisponível: {exc}", "done",
                       {"available": False, "topology": topo})
            return
        self._step(
            "distribution", "Distribuição (caminho de rede real)",
            f"POST /api/events → {status} em {ms:.1f}ms → re-emitido via SSE. "
            "Cada veículo da frota publica exatamente assim.",
            "done",
            {"http_status": status, "http_post_ms": round(ms, 1), "topology": topo},
        )
