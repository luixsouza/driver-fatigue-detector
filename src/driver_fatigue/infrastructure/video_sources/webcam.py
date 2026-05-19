from __future__ import annotations

import time

import cv2
import numpy as np

from driver_fatigue.domain.entities import Frame


def _try_open(
    device_index: int,
    backend: int,
    *,
    width: int,
    height: int,
    fps: int,
    use_mjpg: bool,
) -> cv2.VideoCapture | None:
    """Abre + configura + valida lendo dois frames. Retorna None se vier preto."""
    cap = cv2.VideoCapture(device_index, backend)
    if not cap.isOpened():
        return None
    if use_mjpg:
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        except Exception:
            pass
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    # Descarta o primeiro frame (driver às vezes solta um buffer estale)
    # e valida que o segundo tem conteúdo real.
    cap.read()
    ok, img = cap.read()
    if not ok or img is None or img.size == 0:
        cap.release()
        return None
    # Frame totalmente preto = driver/codec não tá entregando — descarta.
    if float(np.mean(img)) < 1.0:
        cap.release()
        return None
    return cap


class WebcamVideoSource:
    def __init__(
        self,
        device_index: int = 0,
        *,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ) -> None:
        # Ordem das tentativas: queremos 30fps em HD mas sem entregar frame
        # preto. Cada combinação é testada com leitura real antes de aceitar.
        #   1) DSHOW + MJPG: caminho rápido na maioria das webcams Windows.
        #   2) MSMF + MJPG: alguns drivers só funcionam em Media Foundation.
        #   3) ANY + MJPG: deixa OpenCV escolher.
        #   4) ANY sem MJPG: fallback final (YUY2 — pode capar fps mas ao
        #      menos entrega imagem).
        candidates: list[tuple[int, bool]] = []
        if hasattr(cv2, "CAP_DSHOW"):
            candidates.append((cv2.CAP_DSHOW, True))
        if hasattr(cv2, "CAP_MSMF"):
            candidates.append((cv2.CAP_MSMF, True))
        candidates.append((cv2.CAP_ANY, True))
        candidates.append((cv2.CAP_ANY, False))

        cap: cv2.VideoCapture | None = None
        for backend, use_mjpg in candidates:
            cap = _try_open(
                device_index, backend,
                width=width, height=height, fps=fps, use_mjpg=use_mjpg,
            )
            if cap is not None:
                break

        if cap is None:
            raise RuntimeError(f"Não foi possível abrir webcam {device_index}")

        self._cap = cap
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
