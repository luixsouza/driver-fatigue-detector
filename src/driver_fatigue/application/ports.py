"""Interfaces (ports) que a Application exige da Infrastructure."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueEvent,
    FatigueState,
    Frame,
)


@runtime_checkable
class VideoSourcePort(Protocol):
    def read(self) -> Frame | None:
        """Retorna o próximo Frame ou None quando terminou."""
        ...

    def release(self) -> None:
        """Libera recursos (câmera, arquivo, conexão)."""
        ...


@runtime_checkable
class FaceDetectorPort(Protocol):
    def detect(self, frame: Frame) -> list[FaceLandmarks]:
        """Lista de rostos detectados no frame; vazia se nenhum."""
        ...


@runtime_checkable
class AlertSinkPort(Protocol):
    def notify(self, event: FatigueEvent) -> None:
        """Chamado quando severity vira 'alert'."""
        ...

    def on_recovery(self, frame_index: int) -> None:
        """Chamado quando severity volta a 'normal' após 'alert'."""
        ...


@runtime_checkable
class FramePresenterPort(Protocol):
    def present(
        self,
        frame: Frame,
        landmarks: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        """Renderiza/armazena o frame com overlays."""
        ...

    def should_stop(self) -> bool:
        """True se o usuário solicitou encerramento (ex.: tecla 'q')."""
        ...

    def close(self) -> None:
        """Libera recursos (janelas, arquivos)."""
        ...
