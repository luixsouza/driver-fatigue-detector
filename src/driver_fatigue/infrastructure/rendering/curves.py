from __future__ import annotations

from typing import Sequence

import numpy as np

from driver_fatigue.domain.entities import Point


def catmull_rom_closed(
    points: Sequence[Point],
    steps_per_segment: int = 20,
) -> np.ndarray:
    """Catmull-Rom spline fechado passando por todos os pontos.

    Retorna array shape (N*steps_per_segment, 2) em float32.
    Se steps_per_segment==0, retorna apenas os pontos originais.
    """
    if len(points) < 4:
        raise ValueError("Catmull-Rom requer ao menos 4 pontos")

    arr = np.array([[p.x, p.y] for p in points], dtype=np.float32)
    if steps_per_segment == 0:
        return arr

    n = len(arr)
    out_segments = []
    for i in range(n):
        p0 = arr[(i - 1) % n]
        p1 = arr[i]
        p2 = arr[(i + 1) % n]
        p3 = arr[(i + 2) % n]
        t = np.linspace(0.0, 1.0, steps_per_segment, endpoint=False, dtype=np.float32)
        t2 = t * t
        t3 = t2 * t
        seg = 0.5 * (
            (2 * p1)
            + (-p0 + p2) * t[:, None]
            + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2[:, None]
            + (-p0 + 3 * p1 - 3 * p2 + p3) * t3[:, None]
        )
        out_segments.append(seg.astype(np.float32))
    return np.concatenate(out_segments, axis=0)
