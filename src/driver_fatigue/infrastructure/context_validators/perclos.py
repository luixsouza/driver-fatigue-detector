"""PERCLOS — Percentage of eye CLOSure over time.

Métrica padrão da literatura de drowsiness detection (NHTSA, NTHU-DDD).
Define-se como a fração do tempo em que o olho ficou fechado (EAR abaixo
de threshold) numa janela temporal — tipicamente 60s.

Implementação: buffer circular leve, cada amostra tem (timestamp, closed_bool).
Amostras fora da janela são descartadas no `ratio()`.
"""
from __future__ import annotations

from collections import deque


class PerclosBuffer:
    def __init__(self, window_seconds: float) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds deve ser positivo")
        self._window = float(window_seconds)
        self._samples: deque[tuple[float, bool]] = deque()

    def add(self, timestamp: float, closed: bool) -> None:
        self._samples.append((timestamp, closed))
        cutoff = timestamp - self._window
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def ratio(self) -> float:
        if not self._samples:
            return 0.0
        closed = sum(1 for _, c in self._samples if c)
        return closed / len(self._samples)

    def sample_count(self) -> int:
        return len(self._samples)
