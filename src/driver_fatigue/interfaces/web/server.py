"""Servidor web do dashboard.

Recebe eventos do detector via HTTP webhook (POST /api/events) e os
distribui para todos os browsers conectados via Server-Sent Events
(GET /api/stream). Serve a página HTML estática em /.

Por padrão, sobe o detector como subprocess (apontado pra si mesmo)
assim que liga — abrir o browser no dashboard já mostra a câmera.

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
import subprocess
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
        if name.endswith(".js"):
            return "application/javascript; charset=utf-8"
        if name.endswith(".css"):
            return "text/css; charset=utf-8"
        if name.endswith(".json"):
            return "application/json"
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
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    last_ping = time.monotonic()
        except (BrokenPipeError, ConnectionResetError):
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
        except (BrokenPipeError, ConnectionResetError):
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
        except (BrokenPipeError, ConnectionResetError):
            raise

    def _sse_send(self, event: dict) -> None:
        line = f"data: {json.dumps(event)}\n\n".encode("utf-8")
        try:
            self.wfile.write(line)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            raise


def _spawn_detector(
    *,
    target_url: str,
    source: str,
    config: str | None = None,
    extra_args: list[str] | None = None,
    api_key: str | None = None,
) -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "driver_fatigue", "run",
        "--source", source,
        "--headless",
        "--dashboard", target_url,
        "--context-validator", "noop",
    ]
    if config is None:
        # config padrão pro demo web: sensível e sem glow
        default_cfg = Path(__file__).resolve().parents[3].parent / "config" / "web-demo.yaml"
        if default_cfg.exists():
            config = str(default_cfg)
    if config:
        cmd.extend(["--config", config])
    if source.startswith("file:"):
        cmd.append("--loop")
    if extra_args:
        cmd.extend(extra_args)
    _log.info("Subindo detector: %s", " ".join(cmd))
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    env = os.environ.copy()
    if api_key:
        env["DRIVER_FATIGUE_WEB__API_KEY"] = api_key
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        env=env,
    )


class _DetectorSupervisor:
    """Mantém o detector vivo: respawn automático quando ele sai
    (caso típico: arquivo de vídeo terminou)."""

    def __init__(
        self,
        target_url: str,
        source: str,
        config: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._target_url = target_url
        self._source = source
        self._config = config
        self._api_key = api_key
        self._proc: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try: self._proc.kill()
                except Exception: pass

    def _loop(self) -> None:
        backoff = 2.0
        while not self._stop.is_set():
            try:
                self._proc = _spawn_detector(
                    target_url=self._target_url, source=self._source,
                    config=self._config, api_key=self._api_key,
                )
            except Exception as exc:
                _log.warning("spawn falhou: %s; tentando novamente em %.1fs", exc, backoff)
                if self._stop.wait(backoff): return
                backoff = min(backoff * 1.5, 30.0)
                continue
            backoff = 2.0
            rc = self._proc.wait()
            if self._stop.is_set():
                return
            _log.info("detector saiu com rc=%s; respawn em 2s", rc)
            if self._stop.wait(2.0):
                return


def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    *,
    spawn_detector: bool = True,
    detector_source: str = "webcam:0",
    detector_config: str | None = None,
    detector_extra_args: list[str] | None = None,
    api_key: str | None = None,
) -> None:
    global _api_key, _started_at
    _api_key = api_key
    _started_at = time.monotonic()
    if api_key is None and host not in ("127.0.0.1", "::1", "localhost"):
        _log.warning(
            "Servindo em %s sem api_key — qualquer um na rede pode publicar eventos/vídeo. "
            "Defina web.api_key em config/*.yaml ou DRIVER_FATIGUE_WEB__API_KEY.",
            host,
        )
    httpd = ThreadingHTTPServer((host, port), _Handler)
    target_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    target_url = f"http://{target_host}:{port}"
    print(f"Driver Fatigue dashboard rodando em {target_url}")
    if api_key:
        print("Auth: X-API-Key obrigatorio em POST /api/events e /api/video/push")

    supervisor: _DetectorSupervisor | None = None
    if spawn_detector:
        supervisor = _DetectorSupervisor(
            target_url=target_url, source=detector_source, config=detector_config,
            api_key=api_key,
        )
        supervisor.start()
        print(f"Detector supervisor iniciado — fonte={detector_source}"
              + (f" config={detector_config}" if detector_config else ""))
    else:
        print("Detector NAO iniciado — rode 'driver-fatigue run --dashboard %s' em outro terminal" % target_url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nFinalizando...")
    finally:
        httpd.shutdown()
        if supervisor is not None:
            supervisor.stop()


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
