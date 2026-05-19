"""Métricas geométricas puras sobre landmarks faciais."""
from __future__ import annotations

import math
from collections.abc import Sequence

from driver_fatigue.domain.entities import Point


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def eye_aspect_ratio(eye: Sequence[Point]) -> float:
    """Razão altura/largura do olho.

    Espera 6 pontos na ordem semântica:
    p0=canto externo, p1=topo-ext, p2=topo-int, p3=canto interno,
    p4=base-int, p5=base-ext.

    Formula: (|p1-p5| + |p2-p4|) / (2 * |p0-p3|)
    """
    if len(eye) != 6:
        raise ValueError(f"eye_aspect_ratio requer 6 pontos, recebeu {len(eye)}")
    width = _dist(eye[0], eye[3])
    if width == 0.0:
        raise ValueError("largura do olho é zero — pontos coincidentes")
    a = _dist(eye[1], eye[5])
    b = _dist(eye[2], eye[4])
    return (a + b) / (2.0 * width)


def mouth_aspect_ratio(mouth: Sequence[Point]) -> float:
    """Razão altura/largura da boca.

    Espera 12 pontos do contorno externo. Largura = |p0 - p6|.
    Altura = média de |p3-p9|, |p2-p10|, |p4-p8|.
    """
    if len(mouth) != 12:
        raise ValueError(f"mouth_aspect_ratio requer 12 pontos, recebeu {len(mouth)}")
    width = _dist(mouth[0], mouth[6])
    if width == 0.0:
        raise ValueError("largura da boca é zero — pontos coincidentes")
    a = _dist(mouth[3], mouth[9])
    b = _dist(mouth[2], mouth[10])
    c = _dist(mouth[4], mouth[8])
    return (a + b + c) / (3.0 * width)
