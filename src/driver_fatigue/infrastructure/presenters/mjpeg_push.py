"""Presenter que envia o frame renderizado pra um servidor de dashboard.

Usa o mesmo `FrameRenderer` da janela OpenCV, então o que aparece no
browser é exatamente o overlay completo (curvas, glow, HUD). Frames são
codificados como JPEG e enviados via POST `multipart/x-mixed-replace`
contínuo. Tolerante a server fora do ar — silencia falhas e segue.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from urllib.parse import urlparse

import cv2
import httpx

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer

_log = logging.getLogger("driver_fatigue.mjpeg_push")


class MjpegStreamPresenter:
    """Envia frames renderizados como JPEG ao endpoint /api/video/push do dashboard.

    O protocolo é simples: cada POST manda um único JPEG no corpo;
    server agrega num stream MJPEG pros browsers conectados.
    """

    def __init__(
        self,
        renderer: FrameRenderer,
        push_url: str,
        jpeg_quality: int = 70,
        max_fps: float = 15.0,
        timeout_seconds: float = 1.0,
        api_key: str | None = None,
    ) -> None:
        self._renderer = renderer
        self._push_url = push_url
        self._jpeg_quality = max(1, min(100, jpeg_quality))
        self._min_interval = 1.0 / max(0.1, max_fps)
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.Client(timeout=timeout_seconds, headers=headers)
        self._last_send_at = 0.0
        self._stop_requested = False
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        now = time.monotonic()
        if now - self._last_send_at < self._min_interval:
            return
        self._last_send_at = now
        rendered = self._renderer.render(frame, landmarks_list, state)
        ok, buf = cv2.imencode(".jpg", rendered, [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality])
        if not ok:
            return
        try:
            self._queue.put_nowait(bytes(buf))
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(bytes(buf))
            except (queue.Empty, queue.Full):
                pass

    def should_stop(self) -> bool:
        return self._stop_requested

    def request_stop(self) -> None:
        self._stop_requested = True

    def close(self) -> None:
        self._stop_requested = True
        try:
            self._queue.put_nowait(b"")
        except queue.Full:
            pass
        try:
            self._worker.join(timeout=1.0)
        except RuntimeError:
            pass
        try:
            self._client.close()
        except Exception:
            pass

    def _loop(self) -> None:
        while not self._stop_requested:
            try:
                payload = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if not payload:
                return
            try:
                self._client.post(
                    self._push_url,
                    content=payload,
                    headers={"Content-Type": "image/jpeg"},
                )
            except httpx.HTTPError as exc:
                _log.debug("push falhou: %s", exc)
