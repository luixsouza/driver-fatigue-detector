from __future__ import annotations

import time

import cv2

from driver_fatigue.domain.entities import Frame


class WebcamVideoSource:
    def __init__(
        self,
        device_index: int = 0,
        *,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ) -> None:
        self._cap = cv2.VideoCapture(device_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir webcam {device_index}")
        # Pede HD; se a câmera não suportar, OpenCV silenciosamente cai pra closest.
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)
        # Buffer pequeno reduz latência de webcam (frame mais recente).
        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        self._index = 0
        self._released = False

    def read(self) -> Frame | None:
        ok, img = self._cap.read()
        if not ok:
            return None
        frame = Frame(image=img, timestamp=time.monotonic(), index=self._index)
        self._index += 1
        return frame

    def release(self) -> None:
        if not self._released:
            self._cap.release()
            self._released = True
