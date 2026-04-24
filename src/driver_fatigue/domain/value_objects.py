from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FatigueThresholds:
    ear_threshold: float = 0.25
    mar_threshold: float = 0.60
    consecutive_frames: int = 20
    warning_ratio: float = 0.85

    def __post_init__(self) -> None:
        if not 0.0 < self.warning_ratio <= 1.0:
            raise ValueError("warning_ratio deve estar em (0, 1]")
        if self.consecutive_frames < 0:
            raise ValueError("consecutive_frames não pode ser negativo")
        if self.ear_threshold <= 0:
            raise ValueError("ear_threshold deve ser positivo")
        if self.mar_threshold <= 0:
            raise ValueError("mar_threshold deve ser positivo")
