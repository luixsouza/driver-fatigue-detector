from __future__ import annotations

from dataclasses import dataclass

import numpy as np


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
