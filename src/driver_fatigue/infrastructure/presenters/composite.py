from __future__ import annotations

import logging

from driver_fatigue.application.ports import FramePresenterPort
from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame

_log = logging.getLogger("driver_fatigue.presenters")


class CompositePresenter:
    """Fan-out para múltiplos presenters. Tolerante a falhas em close."""

    def __init__(self, *presenters: FramePresenterPort) -> None:
        self._presenters = presenters

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        for p in self._presenters:
            p.present(frame, landmarks_list, state)

    def should_stop(self) -> bool:
        return any(p.should_stop() for p in self._presenters)

    def close(self) -> None:
        for p in self._presenters:
            try:
                p.close()
            except Exception:
                _log.exception("presenter %s falhou em close", type(p).__name__)
