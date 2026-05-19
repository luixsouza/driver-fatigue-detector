from __future__ import annotations

import contextlib
import signal

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame


class HeadlessPresenter:
    """Presenter no-op para modo servidor: não desenha, apenas captura SIGINT."""

    def __init__(self, install_signal_handler: bool = True) -> None:
        self._stop_requested = False
        if install_signal_handler:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(signal.SIGINT, self._on_signal)

    def _on_signal(self, signum, frame) -> None:
        self._stop_requested = True

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        pass

    def request_stop(self) -> None:
        self._stop_requested = True

    def should_stop(self) -> bool:
        return self._stop_requested

    def close(self) -> None:
        pass
