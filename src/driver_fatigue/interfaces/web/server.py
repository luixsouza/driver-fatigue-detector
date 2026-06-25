"""Servidor web do dashboard.

Recebe eventos do detector via HTTP webhook (POST /api/events) e os
distribui para todos os browsers conectados via Server-Sent Events
(GET /api/stream). Serve a página HTML estática em /.

Por padrão, embute o detector na **mesma thread pool do servidor** (sem
subprocess, sem HTTP loopback) — o caminho rápido. POST /api/events e
/api/video/push continuam disponíveis pra cenários ubíquos onde um
detector remoto publica pro dashboard de outra máquina.

Stack mínimo da stdlib: nenhuma dep extra além do que ja temos no
projeto. Usa http.server + threading + fila por cliente.

Uso:
    driver-fatigue web --port 8000                  # liga detector + dashboard
    driver-fatigue web --port 8000 --no-detector    # só o dashboard, sem detector
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_log = logging.getLogger("driver_fatigue.web")
STATIC_DIR = Path(__file__).parent / "static"

_subscribers_lock = threading.Lock()
_subscribers: list[queue.Queue] = []
_last_event: dict[str, Any] | None = None

_video_lock = threading.Lock()
_video_subscribers: list[queue.Queue] = []
_last_jpeg: bytes | None = None
_last_jpeg_at: float = 0.0

_api_key: str | None = None
_started_at: float = 0.0
_last_event_at: float = 0.0

# Snapshot dos sliders simulados (BPM, volante, tempo, hora).
# Acessado pelo POST /api/inputs (escrita), GET /api/inputs (leitura),
# e pelo _InProcessFramePresenter (leitura a cada frame).
_simulated_lock = threading.Lock()
_simulated_inputs: dict[str, float] = {
    "bpm": 75.0,
    "steering_noise": 0.1,
    "hours_driving": 0.0,
    "hour_of_day": 12.0,
}

_INPUT_RANGES: dict[str, tuple[float, float]] = {
    "bpm": (40.0, 120.0),
    "steering_noise": (0.0, 1.0),
    "hours_driving": (0.0, 10.0),
    "hour_of_day": (0.0, 23.99),
}

# Thresholds de detecção live-mutáveis pelo /api/inputs. São distintos de
# _simulated_inputs porque modificam a regra de decisão real (EAR/MAR/pitch),
# não só a camada secundária do FatigueIndex.
_thresholds_lock = threading.Lock()
_runtime_thresholds: dict[str, float] = {
    "ear_threshold": 0.19,
    "mar_threshold": 0.65,
    "consecutive_frames": 22.0,
    "head_drop_pitch_deg": 22.0,
}
_THRESHOLD_RANGES: dict[str, tuple[float, float]] = {
    "ear_threshold": (0.10, 0.35),
    "mar_threshold": (0.30, 0.90),
    "consecutive_frames": (5.0, 60.0),
    "head_drop_pitch_deg": (10.0, 45.0),
}
# Campos inteiros — recebidos como float mas convertidos antes de aplicar.
_THRESHOLD_INT_FIELDS: set[str] = {"consecutive_frames"}

# Referência ao DetectFatigueUseCase ativo, setada pelo _EmbeddedDetector
# após cada respawn. None até o detector subir.
_active_detect_uc = None
# True quando o usuário (ou demo) tocou em algum threshold. Na primeira
# subida do detector, se _thresholds_dirty=False, sincronizamos o snapshot
# do server a partir do YAML do detector (em vez de sobrescrever o YAML
# com os defaults hardcoded acima).
_thresholds_dirty = False


def _get_simulated_snapshot() -> dict[str, float]:
    with _simulated_lock:
        return dict(_simulated_inputs)


def _update_simulated(updates: dict) -> None:
    with _simulated_lock:
        for key, lo_hi in _INPUT_RANGES.items():
            if key in updates:
                val = updates[key]
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue
                lo, hi = lo_hi
                _simulated_inputs[key] = max(lo, min(hi, val))


def _get_thresholds_snapshot() -> dict[str, float]:
    with _thresholds_lock:
        return dict(_runtime_thresholds)


def _update_thresholds(updates: dict) -> dict[str, float]:
    """Atualiza thresholds runtime + propaga pro detector ativo se houver.
    Retorna snapshot dos thresholds após o update."""
    applied: dict[str, float] = {}
    global _thresholds_dirty
    with _thresholds_lock:
        for key, lo_hi in _THRESHOLD_RANGES.items():
            if key in updates:
                val = updates[key]
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue
                lo, hi = lo_hi
                clamped = max(lo, min(hi, val))
                if key in _THRESHOLD_INT_FIELDS:
                    clamped = int(round(clamped))
                _runtime_thresholds[key] = clamped
                applied[key] = clamped
        if applied:
            _thresholds_dirty = True
        snapshot = dict(_runtime_thresholds)
    # Propaga ao use case ativo fora do lock pra evitar contenção.
    if applied and _active_detect_uc is not None:
        try:
            _active_detect_uc.update_thresholds(**applied)
        except Exception as exc:
            _log.warning("falha aplicando thresholds ao detector: %s", exc)
    return snapshot


# Cenario scriptado pra demonstracao. Anda em 10Hz interpolando entre
# checkpoints. Singleton: so um demo roda por vez (segunda chamada → 409).
_demo_runner_lock = threading.Lock()
_demo_runner: _DemoScenarioRunner | None = None

# Tour Ubiquo (demonstracao automatica das 5 propriedades invisiveis).
# Singleton tambem. Ver interfaces/web/ubiquity_tour.py.
_tour_runner_lock = threading.Lock()
_tour_runner: Any = None
_TOUR_STEPS = ("fault", "heterogeneity", "privacy", "security", "distribution")

# Referencia ao detector embutido + contador de geracao (incrementa a cada
# respawn). Usados pelo passo "tolerancia a falhas" do Tour Ubiquo pra
# derrubar o detector e medir quanto tempo o supervisor leva pra recuperar.
_active_runner: _EmbeddedDetectorRunner | None = None
_detector_gen_lock = threading.Lock()
_detector_generation = 0

# Host/porta efetivos do servidor — usados pelos passos de loopback do tour.
_server_host = "127.0.0.1"
_server_port = 8000


def _inject_detector_fault(timeout: float = 15.0) -> dict[str, Any]:
    """Derruba o run atual do detector e espera o supervisor respawnar.

    Retorna {available, respawn_seconds}. Usado pelo Tour Ubiquo."""
    runner = _active_runner
    if runner is None:
        return {"available": False}
    with _detector_gen_lock:
        gen0 = _detector_generation
    t0 = time.monotonic()
    runner.force_restart()
    deadline = t0 + timeout
    while time.monotonic() < deadline:
        with _detector_gen_lock:
            if _detector_generation > gen0:
                return {"available": True, "respawn_seconds": time.monotonic() - t0}
        time.sleep(0.05)
    return {"available": True, "respawn_seconds": None, "timed_out": True}


def _topology_snapshot() -> dict[str, Any]:
    """Estado vivo dos componentes distribuidos — alimenta o passo de
    distribuicao do Tour Ubiquo."""
    now = time.monotonic()
    with _detector_gen_lock:
        gen = _detector_generation
    return {
        "detector_embedded": _active_runner is not None,
        "detector_generation": gen,
        "sse_subscribers": len(_subscribers),
        "video_subscribers": len(_video_subscribers),
        "uptime_seconds": round(now - _started_at, 1) if _started_at > 0 else None,
        "transport": "in-process (fast path) + HTTP POST /api/events (remoto)",
    }


_DEMO_TIMELINE: list[tuple[float, dict[str, float]]] = [
    (0.0,  {"bpm": 75, "steering_noise": 0.10, "hours_driving": 5.0, "hour_of_day": 15.0}),
    (5.0,  {"bpm": 70, "steering_noise": 0.15, "hours_driving": 5.5, "hour_of_day": 15.0}),
    (10.0, {"bpm": 62, "steering_noise": 0.30, "hours_driving": 6.0, "hour_of_day": 15.0}),
    (15.0, {"bpm": 55, "steering_noise": 0.50, "hours_driving": 6.5, "hour_of_day": 15.0}),
    (20.0, {"bpm": 50, "steering_noise": 0.65, "hours_driving": 7.0, "hour_of_day": 3.5}),
    (25.0, {"bpm": 48, "steering_noise": 0.75, "hours_driving": 7.5, "hour_of_day": 3.5}),
    (30.0, {"bpm": 48, "steering_noise": 0.75, "hours_driving": 7.5, "hour_of_day": 3.5}),
]


class _DemoScenarioRunner:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        start = time.monotonic()
        step = 0.1  # 10Hz
        while not self._stop.is_set():
            elapsed = time.monotonic() - start
            if elapsed >= _DEMO_TIMELINE[-1][0]:
                _update_simulated(_DEMO_TIMELINE[-1][1])
                break
            snapshot = self._interpolate(elapsed)
            _update_simulated(snapshot)
            if self._stop.wait(step):
                return

    @staticmethod
    def _interpolate(t: float) -> dict[str, float]:
        # encontra o segmento [t_i, t_{i+1}] que contem t
        for i in range(len(_DEMO_TIMELINE) - 1):
            t0, p0 = _DEMO_TIMELINE[i]
            t1, p1 = _DEMO_TIMELINE[i + 1]
            if t0 <= t < t1:
                frac = (t - t0) / (t1 - t0)
                return {k: p0[k] + (p1[k] - p0[k]) * frac for k in p0}
        return dict(_DEMO_TIMELINE[-1][1])


def _push_jpeg(jpeg: bytes) -> None:
    global _last_jpeg, _last_jpeg_at
    _last_jpeg = jpeg
    _last_jpeg_at = time.monotonic()
    with _video_lock:
        dead: list[queue.Queue] = []
        for q in _video_subscribers:
            try:
                q.put_nowait(jpeg)
            except queue.Full:
                # consumidor lento: dropa o frame mais antigo dele
                try:
                    q.get_nowait()
                    q.put_nowait(jpeg)
                except (queue.Empty, queue.Full):
                    dead.append(q)
        for q in dead:
            _video_subscribers.remove(q)


def _video_subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=2)
    with _video_lock:
        _video_subscribers.append(q)
    return q


def _video_unsubscribe(q: queue.Queue) -> None:
    with _video_lock:
        if q in _video_subscribers:
            _video_subscribers.remove(q)


def _broadcast(event: dict[str, Any]) -> None:
    global _last_event, _last_event_at
    _last_event = event
    _last_event_at = time.monotonic()
    with _subscribers_lock:
        dead: list[queue.Queue] = []
        for q in _subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def _subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=200)
    with _subscribers_lock:
        _subscribers.append(q)
    return q


def _unsubscribe(q: queue.Queue) -> None:
    with _subscribers_lock:
        if q in _subscribers:
            _subscribers.remove(q)


class _Handler(BaseHTTPRequestHandler):
    server_version = "DriverFatigueWeb/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        _log.debug("%s - " + format, self.address_string(), *args)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path == "/" or path == "/index.html":
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if path.startswith("/assets/"):
            name = path[1:]  # strip leading slash → "assets/index-XXXX.js"
            mime = self._guess_mime(name)
            self._serve_static(name, mime)
            return
        if path.endswith(".svg") or path.endswith(".png") or path.endswith(".ico"):
            # arquivos da raiz do public/ (ifg-logo.svg, favicons, etc.)
            name = path.lstrip("/")
            mime = self._guess_mime(name)
            self._serve_static(name, mime)
            return
        if path.startswith("/static/"):
            name = path[len("/static/") :]
            mime = self._guess_mime(name)
            self._serve_static(name, mime)
            return
        if path == "/api/stream":
            self._serve_sse()
            return
        if path == "/api/video":
            self._serve_mjpeg()
            return
        if path == "/api/inputs":
            payload = {
                **_get_simulated_snapshot(),
                **_get_thresholds_snapshot(),
            }
            self._json(200, payload)
            return
        if path == "/api/health" or path == "/health":
            now = time.monotonic()
            video_age = now - _last_jpeg_at if _last_jpeg is not None else None
            event_age = now - _last_event_at if _last_event_at > 0 else None
            uptime = now - _started_at if _started_at > 0 else None
            stale_video = video_age is not None and video_age > 5.0
            stale_events = event_age is not None and event_age > 10.0
            no_signal = _last_jpeg is None and _last_event is None
            ok = not (stale_video or stale_events or no_signal)
            last_severity = None
            if _last_event is not None:
                last_severity = _last_event.get("severity")
            self._json(200 if ok else 503, {
                "ok": ok,
                "uptime_seconds": uptime,
                "subscribers": len(_subscribers),
                "video_subscribers": len(_video_subscribers),
                "video_age_seconds": video_age,
                "event_age_seconds": event_age,
                "last_severity": last_severity,
                "auth_required": _api_key is not None,
            })
            return
        self.send_error(404, "not found")

    def _require_auth(self) -> bool:
        if _api_key is None:
            return True
        provided = self.headers.get("X-API-Key")
        if provided == _api_key:
            return True
        self.send_error(401, "missing or invalid X-API-Key")
        return False

    def do_POST(self) -> None:  # noqa: N802
        global _demo_runner, _tour_runner
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        self.path = path
        if self.path == "/api/events":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            if not self._require_auth():
                return
            if not body:
                self.send_error(400, "empty body")
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                self.send_error(400, f"invalid json: {exc}")
                return
            payload.setdefault("received_at", time.time())
            _broadcast(payload)
            self._json(202, {"status": "accepted"})
            return
        if self.path == "/api/video/push":
            length = int(self.headers.get("Content-Length", "0"))
            if length > 5_000_000:
                self.send_error(400, "invalid jpeg size")
                return
            jpeg = self.rfile.read(length) if length > 0 else b""
            if not self._require_auth():
                return
            if not jpeg:
                self.send_error(400, "invalid jpeg size")
                return
            _push_jpeg(jpeg)
            self._json(202, {"status": "accepted"})
            return
        if self.path == "/api/inputs":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            if not self._require_auth():
                return
            if not body:
                self.send_error(400, "empty body")
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                self.send_error(400, f"invalid json: {exc}")
                return
            if not isinstance(payload, dict):
                self.send_error(400, "expected json object")
                return
            _update_simulated(payload)
            _update_thresholds(payload)
            self._json(202, {"status": "accepted"})
            return
        if self.path == "/api/demo/start":
            if not self._require_auth():
                return
            with _demo_runner_lock:
                if _demo_runner is not None and _demo_runner._thread.is_alive():
                    self._json(409, {"error": "demo already running"})
                    return
                _demo_runner = _DemoScenarioRunner()
                _demo_runner.start()
            self._json(202, {"status": "started", "duration_seconds": _DEMO_TIMELINE[-1][0]})
            return
        if self.path == "/api/demo/stop":
            if not self._require_auth():
                return
            with _demo_runner_lock:
                if _demo_runner is None or not _demo_runner._thread.is_alive():
                    self._json(200, {"status": "not_running"})
                    return
                _demo_runner.stop()
                _demo_runner = None
            self._json(202, {"status": "stopped"})
            return
        if self.path == "/api/demo/secure-echo":
            # Endpoint dedicado à demonstração de segurança do Tour Ubiquo.
            # Exige X-Demo-Key fixa (independe da web.api_key) → 401/200
            # determinístico. Espelha o mesmo mecanismo de _require_auth.
            from driver_fatigue.interfaces.web.ubiquity_tour import DEMO_SECURE_KEY
            length = int(self.headers.get("Content-Length", "0"))
            if length > 0:
                self.rfile.read(length)
            if self.headers.get("X-Demo-Key") == DEMO_SECURE_KEY:
                self._json(200, {"status": "ok", "authenticated": True})
            else:
                self._json(401, {"status": "unauthorized"})
            return
        if self.path == "/api/demo/tour/start":
            if not self._require_auth():
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length > 0:
                self.rfile.read(length)
            from driver_fatigue.interfaces.web.ubiquity_tour import UbiquityTourRunner
            with _tour_runner_lock:
                if _tour_runner is not None and _tour_runner.is_alive():
                    self._json(409, {"error": "tour already running"})
                    return
                demo_dir = Path(
                    os.environ.get("DRIVER_FATIGUE_DEMO_DIR")
                    or (Path.cwd() / "demo-artifacts")
                )
                _tour_runner = UbiquityTourRunner(
                    broadcast=_broadcast,
                    host=_server_host,
                    port=_server_port,
                    api_key=_api_key,
                    fault_injector=_inject_detector_fault,
                    topology_probe=_topology_snapshot,
                    demo_dir=demo_dir,
                )
                _tour_runner.start()
            self._json(202, {"status": "started", "steps": list(_TOUR_STEPS)})
            return
        if self.path == "/api/demo/tour/stop":
            if not self._require_auth():
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length > 0:
                self.rfile.read(length)
            with _tour_runner_lock:
                if _tour_runner is None or not _tour_runner.is_alive():
                    self._json(200, {"status": "not_running"})
                    return
                _tour_runner.stop()
                _tour_runner = None
            self._json(202, {"status": "stopped"})
            return
        self.send_error(404, "not found")

    def _serve_static(self, name: str, mime: str) -> None:
        target = (STATIC_DIR / name).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self.send_error(403, "forbidden")
            return
        if not target.exists() or not target.is_file():
            self.send_error(404, "not found")
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _guess_mime(self, name: str) -> str:
        if name.endswith(".html"):
            return "text/html; charset=utf-8"
        if name.endswith(".js") or name.endswith(".mjs"):
            return "application/javascript; charset=utf-8"
        if name.endswith(".css"):
            return "text/css; charset=utf-8"
        if name.endswith(".json"):
            return "application/json"
        if name.endswith(".svg"):
            return "image/svg+xml"
        if name.endswith(".png"):
            return "image/png"
        if name.endswith(".woff2"):
            return "font/woff2"
        if name.endswith(".ico"):
            return "image/x-icon"
        return "application/octet-stream"

    def _json(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        q = _subscribe()
        try:
            if _last_event is not None:
                self._sse_send(_last_event)
            last_ping = time.monotonic()
            while True:
                try:
                    event = q.get(timeout=15.0)
                    self._sse_send(event)
                except queue.Empty:
                    pass
                if time.monotonic() - last_ping > 15.0:
                    try:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                        return
                    last_ping = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        finally:
            _unsubscribe(q)

    def _serve_mjpeg(self) -> None:
        boundary = "fatigueframe"
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        q = _video_subscribe()
        try:
            if _last_jpeg is not None:
                self._mjpeg_send(boundary, _last_jpeg)
            while True:
                try:
                    jpeg = q.get(timeout=10.0)
                except queue.Empty:
                    continue
                self._mjpeg_send(boundary, jpeg)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        finally:
            _video_unsubscribe(q)

    def _mjpeg_send(self, boundary: str, jpeg: bytes) -> None:
        head = (
            f"--{boundary}\r\n"
            f"Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(jpeg)}\r\n\r\n"
        ).encode("ascii")
        try:
            self.wfile.write(head)
            self.wfile.write(jpeg)
            self.wfile.write(b"\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            raise

    def _sse_send(self, event: dict) -> None:
        line = f"data: {json.dumps(event)}\n\n".encode()
        try:
            self.wfile.write(line)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            raise


class _QuietThreadingHTTPServer(ThreadingHTTPServer):
    """Suprime tracebacks ruidosas quando o cliente desconecta no meio
    de um stream MJPEG/SSE — comportamento normal de browser, nao bug."""

    def handle_error(self, request, client_address):  # noqa: ARG002
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


class _InProcessAlertSink:
    """Sink in-memory que despeja eventos direto nas subscriptions do SSE.

    Substitui o HttpWebhookSink quando o detector roda no mesmo processo do
    web server — economiza JSON encode/decode + round-trip HTTP loopback."""

    def __init__(self, evaluator=None) -> None:
        from driver_fatigue.infrastructure.index_evaluators.noop import NoOpIndexEvaluator
        self._evaluator = evaluator or NoOpIndexEvaluator()

    def notify(self, event) -> None:
        # mantem evento simples; sink externo nao recebe fatigue_index
        _broadcast({
            "event": "fatigue_alert",
            "timestamp": event.timestamp,
            "frame_index": event.frame_index,
            "ear": event.state.ear,
            "mar": event.state.mar,
            "severity": event.state.severity,
            "consecutive_frames": event.state.consecutive_frames,
        })

    def on_recovery(self, frame_index: int) -> None:
        _broadcast({
            "event": "fatigue_recovery",
            "timestamp": 0.0,
            "frame_index": frame_index,
        })

    def publish_state(self, frame, state) -> None:
        from driver_fatigue.domain.fatigue_index import FatigueInputs
        baseline = state.baseline
        sim = _get_simulated_snapshot()
        # normalizacoes
        ear_rest = max(baseline.ear_rest, 0.05) if baseline.sample_count > 0 else 0.30
        mar_std = max(baseline.mar_std, 0.04) if baseline.sample_count > 0 else 0.04
        mar_rest = baseline.mar_rest if baseline.sample_count > 0 else 0.20
        ear_norm = max(0.0, min(1.0, state.ear / ear_rest))
        mar_norm = max(0.0, min(1.0, (state.mar - mar_rest) / (mar_std * 3 + 1e-6)))
        inputs = FatigueInputs(
            ear_norm=ear_norm, mar_norm=mar_norm,
            head_drop_frames=state.head_drop_frames,
            consecutive_eyes_closed=state.consecutive_frames,
            bpm=sim["bpm"], steering_noise=sim["steering_noise"],
            hours_driving=sim["hours_driving"], hour_of_day=sim["hour_of_day"],
        )
        idx = self._evaluator.compute(inputs)
        _broadcast({
            "event": "state",
            "timestamp": frame.timestamp,
            "frame_index": frame.index,
            "ear": state.ear,
            "mar": state.mar,
            "severity": state.severity,
            "consecutive_frames": state.consecutive_frames,
            "calibrating": (
                baseline.sample_count > 0 and baseline.sample_count < 30
            ),
            "calibration_progress": min(1.0, baseline.sample_count / 45.0),
            "quality_ok": state.quality.trustworthy,
            "quality_reason": state.quality.reason,
            "fatigue_index": idx.value,
            "index_severity": idx.severity,
            "explain": idx.explain,
            "top_contributors": list(idx.top_contributors),
            "critical": idx.critical,
        })


class _InProcessFramePresenter:
    """Presenter in-memory: renderiza overlay + encoda JPEG e publica no
    buffer do MJPEG sem POST de loopback. Throttled por max_fps."""

    def __init__(self, renderer, *, max_fps: float = 30.0, jpeg_quality: int = 88) -> None:
        import cv2  # local pra reduzir import cost de quem só usa SSE
        self._cv2 = cv2
        self._renderer = renderer
        self._jpeg_quality = max(1, min(100, jpeg_quality))
        self._min_interval = 1.0 / max(0.1, max_fps)
        self._last_send_at = 0.0
        self._stop_requested = False

    def present(self, frame, faces, state) -> None:
        now = time.monotonic()
        if now - self._last_send_at < self._min_interval:
            return
        self._last_send_at = now
        rendered = self._renderer.render(frame, faces, state)
        ok, buf = self._cv2.imencode(
            ".jpg", rendered,
            [int(self._cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality],
        )
        if ok:
            _push_jpeg(bytes(buf))

    def should_stop(self) -> bool:
        return self._stop_requested

    def request_stop(self) -> None:
        self._stop_requested = True

    def close(self) -> None:
        self._stop_requested = True


class _EmbeddedDetectorRunner:
    """Roda o use case do detector numa daemon thread do mesmo processo.

    Respawn automático se o use case sair (arquivo de vídeo terminou,
    câmera caiu, etc.) — backoff exponencial até 30s."""

    def __init__(
        self,
        *,
        source: str,
        config_path: Path | None,
    ) -> None:
        self._source = source
        self._config_path = config_path
        self._stop = threading.Event()
        self._presenter: _InProcessFramePresenter | None = None
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._presenter is not None:
            self._presenter.request_stop()

    def force_restart(self) -> None:
        """Faz o run atual terminar (sem parar o supervisor) → respawn.

        Diferente de stop(): não seta self._stop, então o loop respawna o
        detector. Usado pelo Tour Ubiquo pra demonstrar tolerância a falhas."""
        if self._presenter is not None:
            self._presenter.request_stop()

    def _build_settings(self):
        from driver_fatigue.config.settings import (
            AppSettings,
        )
        cfg = self._config_path
        if cfg is None:
            default_cfg = Path(__file__).resolve().parents[3].parent / "config" / "web-demo.yaml"
            if default_cfg.exists():
                cfg = default_cfg
        settings = (
            AppSettings.from_yaml(cfg) if cfg and cfg.exists() else AppSettings()
        )
        source = _parse_source_str(self._source)
        if source.kind == "file":
            source = source.model_copy(update={"loop": True})
        return settings.model_copy(update={
            "source": source,
            "headless": True,
            # Sinks reais ficam vazios — o InProcessAlertSink injetado já cobre
            # o dashboard, e som/MQTT/JSONL não fazem sentido pro web-embed.
            "sinks": [],
        })

    def _run_once(self) -> None:
        from driver_fatigue.bootstrap import (
            _build_index_evaluator,
            _build_renderer,
            build_monitor_use_case,
        )
        settings = self._build_settings()
        renderer = _build_renderer(settings)
        self._presenter = _InProcessFramePresenter(
            renderer,
            max_fps=settings.dashboard_stream.max_fps,
            jpeg_quality=settings.dashboard_stream.jpeg_quality,
        )
        evaluator = _build_index_evaluator(settings)
        sink = _InProcessAlertSink(evaluator=evaluator)
        uc = build_monitor_use_case(
            settings=settings,
            sink_override=sink,
            presenter_override=self._presenter,
        )
        # Registra o DetectFatigueUseCase ativo pra /api/inputs mexer
        # ear_threshold/mar_threshold/etc em runtime.
        global _active_detect_uc, _detector_generation
        _active_detect_uc = uc._detect
        with _detector_gen_lock:
            _detector_generation += 1
        if _thresholds_dirty:
            # Usuário já mexeu sliders — aplica o snapshot da UI no detector.
            _active_detect_uc.update_thresholds(**_get_thresholds_snapshot())
        else:
            # Primeira subida — sincroniza snapshot do server a partir do
            # YAML do detector pra UI refletir a verdade.
            t = _active_detect_uc.thresholds
            with _thresholds_lock:
                _runtime_thresholds["ear_threshold"] = t.ear_threshold
                _runtime_thresholds["mar_threshold"] = t.mar_threshold
                _runtime_thresholds["consecutive_frames"] = float(t.consecutive_frames)
                _runtime_thresholds["head_drop_pitch_deg"] = t.head_drop_pitch_deg
        try:
            uc.run()
        finally:
            _active_detect_uc = None

    def _loop(self) -> None:
        backoff = 2.0
        while not self._stop.is_set():
            try:
                self._run_once()
            except Exception as exc:
                _log.warning(
                    "detector embutido caiu: %s; respawn em %.1fs", exc, backoff,
                )
                if self._stop.wait(backoff):
                    return
                backoff = min(backoff * 1.5, 30.0)
                continue
            backoff = 2.0
            if self._stop.is_set():
                return
            _log.info("detector embutido finalizou; respawn em 2s")
            if self._stop.wait(2.0):
                return


def _parse_source_str(arg: str):
    """Reaproveita o parsing do CLI para 'webcam:N' | 'file:path' | 'rtsp://...'."""
    from driver_fatigue.interfaces.cli.main import _parse_source
    return _parse_source(arg)


def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    *,
    spawn_detector: bool = True,
    detector_source: str = "webcam:0",
    detector_config: str | None = None,
    detector_extra_args: list[str] | None = None,  # noqa: ARG001 (compat)
    api_key: str | None = None,
) -> None:
    global _api_key, _started_at, _server_host, _server_port
    _api_key = api_key
    _started_at = time.monotonic()
    _server_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    _server_port = port
    if api_key is None and host not in ("127.0.0.1", "::1", "localhost"):
        _log.warning(
            "Servindo em %s sem api_key — qualquer um na rede pode publicar eventos/vídeo. "
            "Defina web.api_key em config/*.yaml ou DRIVER_FATIGUE_WEB__API_KEY.",
            host,
        )
    httpd = _QuietThreadingHTTPServer((host, port), _Handler)
    target_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    target_url = f"http://{target_host}:{port}"
    print(f"Driver Fatigue dashboard rodando em {target_url}")
    if api_key:
        print("Auth: X-API-Key obrigatorio em POST /api/events e /api/video/push")

    global _active_runner
    runner: _EmbeddedDetectorRunner | None = None
    if spawn_detector:
        cfg_path = Path(detector_config) if detector_config else None
        runner = _EmbeddedDetectorRunner(
            source=detector_source,
            config_path=cfg_path,
        )
        _active_runner = runner
        runner.start()
        print(f"Detector embutido (in-process) iniciado — fonte={detector_source}"
              + (f" config={detector_config}" if detector_config else ""))
    else:
        print(f"Detector NAO iniciado — rode 'driver-fatigue run --dashboard {target_url}' em outro terminal")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nFinalizando...")
    finally:
        httpd.shutdown()
        if runner is not None:
            runner.stop()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="driver-fatigue-web")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--source", default="webcam:0",
                   help="fonte do detector embutido (webcam:N | file:path | rtsp://...)")
    p.add_argument("--no-detector", action="store_true",
                   help="nao sobe o detector automaticamente")
    p.add_argument("--api-key", default=None,
                   help="exige X-API-Key em POSTs sensíveis (ou DRIVER_FATIGUE_WEB__API_KEY)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    api_key = args.api_key or os.environ.get("DRIVER_FATIGUE_WEB__API_KEY")
    serve(
        host=args.host,
        port=args.port,
        spawn_detector=not args.no_detector,
        detector_source=args.source,
        api_key=api_key,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
