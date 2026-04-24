from __future__ import annotations

import time
from pathlib import Path

import cv2

from driver_fatigue.domain.entities import Frame


class FileVideoSource:
    """Lê frames de um arquivo de vídeo. Opcionalmente faz loop ao chegar ao fim."""

    def __init__(self, path: Path, loop: bool = False) -> None:
        self._path = Path(path)
        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir vídeo {self._path}")
        self._loop = loop
        self._index = 0
        self._exhausted = False
        self._released = False

    def read(self) -> Frame | None:
        if self._released or self._exhausted:
            return None
        ok, img = self._cap.read()
        if not ok:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, img = self._cap.read()
                if not ok:
                    self._exhausted = True
                    return None
            else:
                self._exhausted = True
                return None
        frame = Frame(image=img, timestamp=time.monotonic(), index=self._index)
        self._index += 1
        return frame

    def release(self) -> None:
        if not self._released:
            self._cap.release()
            self._released = True
