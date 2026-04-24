from __future__ import annotations

import logging
from pathlib import Path

import cv2

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer

_log = logging.getLogger("driver_fatigue.recorder")


class FileRecorderPresenter:
    """Grava MP4 com overlay. Inicializa o writer no primeiro present() (shape conhecido)."""

    def __init__(
        self,
        renderer: FrameRenderer,
        output_path: Path,
        fps: int = 30,
        codec: str = "mp4v",
    ) -> None:
        self._renderer = renderer
        self._output_path = Path(output_path)
        self._fps = fps
        self._codec = codec
        self._writer: cv2.VideoWriter | None = None
        self._disabled = False
        self._closed = False

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        if self._disabled:
            return
        rendered = self._renderer.render(frame, landmarks_list, state)
        if self._writer is None:
            h, w = rendered.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*self._codec)
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = cv2.VideoWriter(
                str(self._output_path), fourcc, self._fps, (w, h),
            )
            if not self._writer.isOpened():
                _log.warning(
                    "VideoWriter falhou em abrir %s com codec %s; gravacao desativada",
                    self._output_path, self._codec,
                )
                self._writer = None
                self._disabled = True
                return
        self._writer.write(rendered)

    def should_stop(self) -> bool:
        return False

    def close(self) -> None:
        if self._closed:
            return
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        self._closed = True
