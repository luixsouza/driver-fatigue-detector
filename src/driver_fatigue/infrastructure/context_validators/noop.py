from __future__ import annotations

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.domain.value_objects import ContextVerdict


class NoopContextValidator:
    """Valida tudo: 'sim, está sonolento'. Mantém o comportamento Fase 2."""

    def confirm_drowsy(
        self,
        frame: Frame,
        landmarks: FaceLandmarks,
        state: FatigueState,
    ) -> ContextVerdict:
        return ContextVerdict.confirm(reason="noop")
