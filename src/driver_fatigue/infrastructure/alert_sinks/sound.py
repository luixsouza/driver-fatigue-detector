from __future__ import annotations

from pathlib import Path

import pygame

from driver_fatigue.domain.entities import FatigueEvent


class SoundSink:
    def __init__(self, sound_path: Path, loops: int = -1) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self._sound = pygame.mixer.Sound(str(sound_path))
        self._loops = loops
        self._playing = False

    def notify(self, event: FatigueEvent) -> None:
        if self._playing:
            return
        self._sound.play(loops=self._loops)
        self._playing = True

    def on_recovery(self, frame_index: int) -> None:
        if self._playing:
            self._sound.stop()
            self._playing = False
