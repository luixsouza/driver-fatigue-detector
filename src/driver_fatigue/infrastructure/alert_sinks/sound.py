from __future__ import annotations

import time
from pathlib import Path

import pygame

from driver_fatigue.domain.entities import FatigueEvent


class SoundSink:
    """Toca alarme em loop com **rampa de volume** e **cooldown**.

    - `start_volume` (0.0-1.0) → `peak_volume` (0.0-1.0) ao longo de
      `ramp_seconds`, atualizado no método `tick()` (chamado pelo monitor
      a cada frame ou pelo próprio evento; tolerante a ausência).
    - Após `on_recovery`, fica em silêncio por `cooldown_seconds` antes
      de aceitar nova `notify()`. Evita "tac-tac-tac" se o sinal oscilar.
    """

    def __init__(
        self,
        sound_path: Path,
        loops: int = -1,
        *,
        start_volume: float = 0.4,
        peak_volume: float = 1.0,
        ramp_seconds: float = 1.5,
        cooldown_seconds: float = 2.0,
        clock: callable = time.monotonic,
    ) -> None:
        if not (0.0 <= start_volume <= 1.0):
            raise ValueError("start_volume fora de [0,1]")
        if not (0.0 <= peak_volume <= 1.0):
            raise ValueError("peak_volume fora de [0,1]")
        if start_volume > peak_volume:
            raise ValueError("start_volume não pode ser maior que peak_volume")
        if ramp_seconds < 0:
            raise ValueError("ramp_seconds não pode ser negativo")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds não pode ser negativo")
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self._sound = pygame.mixer.Sound(str(sound_path))
        self._loops = loops
        self._playing = False
        self._start_volume = start_volume
        self._peak_volume = peak_volume
        self._ramp_seconds = ramp_seconds
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._play_started_at: float | None = None
        self._silenced_until: float | None = None

    def notify(self, event: FatigueEvent) -> None:
        now = self._clock()
        if self._silenced_until is not None and now < self._silenced_until:
            return
        if self._playing:
            self._update_ramp(now)
            return
        self._sound.set_volume(self._start_volume)
        self._sound.play(loops=self._loops)
        self._playing = True
        self._play_started_at = now

    def on_recovery(self, frame_index: int) -> None:
        if self._playing:
            self._sound.stop()
            self._playing = False
        self._play_started_at = None
        self._silenced_until = self._clock() + self._cooldown_seconds

    def tick(self) -> None:
        """Pode ser chamado por loop externo para atualizar volume sem evento novo."""
        if self._playing:
            self._update_ramp(self._clock())

    def _update_ramp(self, now: float) -> None:
        if self._play_started_at is None or self._ramp_seconds <= 0:
            self._sound.set_volume(self._peak_volume)
            return
        elapsed = max(0.0, now - self._play_started_at)
        if elapsed >= self._ramp_seconds:
            self._sound.set_volume(self._peak_volume)
            return
        progress = elapsed / self._ramp_seconds
        vol = self._start_volume + (self._peak_volume - self._start_volume) * progress
        self._sound.set_volume(vol)
