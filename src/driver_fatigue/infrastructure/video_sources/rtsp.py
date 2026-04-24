from __future__ import annotations

import logging
import time

import cv2

from driver_fatigue.domain.entities import Frame

_log = logging.getLogger("driver_fatigue.rtsp")


class RtspVideoSource:
    """Lê frames de um stream RTSP com reconexão exponencial."""

    def __init__(
        self,
        url: str,
        reconnect_attempts: int = 3,
        initial_backoff_seconds: float = 1.0,
    ) -> None:
        self._url = url
        self._reconnect_attempts = reconnect_attempts
        self._initial_backoff = initial_backoff_seconds
        self._cap = self._open()
        self._index = 0
        self._released = False
        self._exhausted = False

    def _open(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir stream RTSP {self._url}")
        return cap

    def _try_reconnect(self) -> bool:
        for attempt in range(self._reconnect_attempts):
            backoff = self._initial_backoff * (2 ** attempt)
            _log.warning("RTSP desconectou; tentativa %d/%d em %.1fs",
                         attempt + 1, self._reconnect_attempts, backoff)
            time.sleep(backoff)
            try:
                self._cap.release()
            except Exception:
                pass
            try:
                self._cap = self._open()
                return True
            except Exception:
                continue
        return False

    def read(self) -> Frame | None:
        if self._released or self._exhausted:
            return None
        ok, img = self._cap.read()
        if not ok:
            if not self._try_reconnect():
                self._exhausted = True
                return None
            ok, img = self._cap.read()
            if not ok:
                self._exhausted = True
                return None
        frame = Frame(image=img, timestamp=time.monotonic(), index=self._index)
        self._index += 1
        return frame

    def release(self) -> None:
        if not self._released:
            try:
                self._cap.release()
            except Exception:
                pass
            self._released = True
