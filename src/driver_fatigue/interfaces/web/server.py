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
    global _last_event
    _last_event = event
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
        if self.path == "/" or self.path == "/index.html":
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if self.path.startswith("/static/"):
            name = self.path[len("/static/") :]
            mime = self._guess_mime(name)
            self._serve_static(name, mime)
            return
        if self.path == "/api/stream":
            self._serve_sse()
            return
        if self.path == "/api/video":
            self._serve_mjpeg()
            return
        if self.path == "/api/health":
            self._json(200, {
                "ok": True,
                "subscribers": len(_subscribers),
                "video_subscribers": len(_video_subscribers),
                "video_age_seconds": (
                    time.monotonic() - _last_jpeg_at if _last_jpeg is not None else None
                ),
            })
            return
        self.send_error(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/events":
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                self.send_error(400, "empty body")
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError as exc:
                self.send_error(400, f"invalid json: {exc}")
                return
            payload.setdefault("received_at", time.time())
            _broadcast(payload)
            self._json(202, {"status": "accepted"})
            return
        if self.path == "/api/video/push":
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 5_000_000:
                self.send_error(400, "invalid jpeg size")
                return
            jpeg = self.rfile.read(length)
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
    extra_args: list[str] | None = None,
) -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "driver_fatigue", "run",
        "--source", source,
        "--headless",
        "--dashboard", target_url,
        "--context-validator", "noop",
    ]
    if extra_args:
        cmd.extend(extra_args)
    _log.info("Subindo detector: %s", " ".join(cmd))
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    *,
    spawn_detector: bool = True,
    detector_source: str = "webcam:0",
    detector_extra_args: list[str] | None = None,
) -> None:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    target_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    target_url = f"http://{target_host}:{port}"
    print(f"Driver Fatigue dashboard rodando em {target_url}")

    detector_proc: subprocess.Popen | None = None
    if spawn_detector:
        try:
            detector_proc = _spawn_detector(
                target_url=target_url,
                source=detector_source,
                extra_args=detector_extra_args,
            )
            print(f"Detector iniciado (PID {detector_proc.pid}) — fonte={detector_source}")
        except Exception as exc:
            _log.warning("Falha ao subir detector automaticamente (%s); siga em modo manual", exc)
    else:
        print("Detector NAO iniciado — rode 'driver-fatigue run --dashboard %s' em outro terminal" % target_url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nFinalizando...")
    finally:
        httpd.shutdown()
        if detector_proc is not None and detector_proc.poll() is None:
            try:
                detector_proc.terminate()
                detector_proc.wait(timeout=3)
            except Exception:
                try: detector_proc.kill()
                except Exception: pass


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="driver-fatigue-web")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--source", default="webcam:0",
                   help="fonte do detector embutido (webcam:N | file:path | rtsp://...)")
    p.add_argument("--no-detector", action="store_true",
                   help="nao sobe o detector automaticamente")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    serve(
        host=args.host,
        port=args.port,
        spawn_detector=not args.no_detector,
        detector_source=args.source,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
