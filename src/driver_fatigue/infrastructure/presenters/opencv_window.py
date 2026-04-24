from __future__ import annotations

import cv2

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer

_WINDOW_NAME = "Detector de Fadiga"


class OpenCvWindowPresenter:
    """Presenter que mostra o frame renderizado em uma janela OpenCV."""

    def __init__(
        self,
        renderer: FrameRenderer,
        window_name: str = _WINDOW_NAME,
    ) -> None:
        self._renderer = renderer
        self._window = window_name
        self._closed = False
        self._stop_requested = False

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        img = self._renderer.render(frame, landmarks_list, state)
        cv2.imshow(self._window, img)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            self._stop_requested = True

    def should_stop(self) -> bool:
        return self._stop_requested

    def close(self) -> None:
        if self._closed:
            return
        try:
            cv2.destroyWindow(self._window)
        except cv2.error:
            pass
        self._closed = True
