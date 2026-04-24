from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

Severity = Literal["normal", "warning", "alert"]


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, eq=False)
class Frame:
    """Frame de vídeo. eq=False porque np.ndarray não suporta ==/hash convencional."""
    image: np.ndarray
    timestamp: float
    index: int


@dataclass(frozen=True, slots=True)
class FaceLandmarks:
    left_eye_contour: tuple[Point, ...]
    right_eye_contour: tuple[Point, ...]
    left_iris: tuple[Point, ...] | None
    right_iris: tuple[Point, ...] | None
    mouth_outer: tuple[Point, ...]
    mouth_inner: tuple[Point, ...]
    face_oval: tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class FatigueState:
    ear: float
    mar: float
    consecutive_frames: int
    is_fatigued: bool
    is_yawning: bool
    severity: Severity

    @classmethod
    def initial(cls) -> "FatigueState":
        return cls(
            ear=0.0,
            mar=0.0,
            consecutive_frames=0,
            is_fatigued=False,
            is_yawning=False,
            severity="normal",
        )


@dataclass(frozen=True, slots=True)
class FatigueEvent:
    timestamp: float
    state: FatigueState
    frame_index: int
