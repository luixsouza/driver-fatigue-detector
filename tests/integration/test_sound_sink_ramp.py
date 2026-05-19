"""Testes da rampa de volume e cooldown do SoundSink."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.sound import SoundSink
from driver_fatigue.config.settings import _DEFAULT_ALARM


def _event():
    return FatigueEvent(
        timestamp=0.0, state=FatigueState.initial(), frame_index=0,
    )


class FakeClock:
    def __init__(self, t0: float = 0.0):
        self.now = t0

    def __call__(self) -> float:
        return self.now


class TestVolumeRamp:
    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_starts_at_start_volume(self, pygame_mock):
        sound = MagicMock()
        pygame_mock.mixer.Sound.return_value = sound
        clock = FakeClock(0.0)
        sink = SoundSink(
            sound_path=_DEFAULT_ALARM,
            start_volume=0.4, peak_volume=1.0, ramp_seconds=2.0,
            cooldown_seconds=0.0, clock=clock,
        )
        sink.notify(_event())
        sound.set_volume.assert_called_with(0.4)

    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_ramps_up_during_window(self, pygame_mock):
        sound = MagicMock()
        pygame_mock.mixer.Sound.return_value = sound
        clock = FakeClock(0.0)
        sink = SoundSink(
            sound_path=_DEFAULT_ALARM,
            start_volume=0.4, peak_volume=1.0, ramp_seconds=2.0,
            cooldown_seconds=0.0, clock=clock,
        )
        sink.notify(_event())
        clock.now = 1.0  # metade da rampa
        sink.tick()
        # Volume deve estar próximo de 0.7
        last_vol = sound.set_volume.call_args[0][0]
        assert 0.65 <= last_vol <= 0.75

    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_reaches_peak_after_ramp(self, pygame_mock):
        sound = MagicMock()
        pygame_mock.mixer.Sound.return_value = sound
        clock = FakeClock(0.0)
        sink = SoundSink(
            sound_path=_DEFAULT_ALARM,
            start_volume=0.4, peak_volume=1.0, ramp_seconds=2.0,
            cooldown_seconds=0.0, clock=clock,
        )
        sink.notify(_event())
        clock.now = 5.0
        sink.tick()
        last_vol = sound.set_volume.call_args[0][0]
        assert last_vol == 1.0


class TestCooldown:
    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_blocks_replay_within_cooldown(self, pygame_mock):
        sound = MagicMock()
        pygame_mock.mixer.Sound.return_value = sound
        clock = FakeClock(0.0)
        sink = SoundSink(
            sound_path=_DEFAULT_ALARM,
            cooldown_seconds=5.0, clock=clock,
            ramp_seconds=0.0,
        )
        sink.notify(_event())
        sink.on_recovery(0)
        sound.play.reset_mock()
        clock.now = 2.0
        sink.notify(_event())
        sound.play.assert_not_called()

    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_allows_replay_after_cooldown(self, pygame_mock):
        sound = MagicMock()
        pygame_mock.mixer.Sound.return_value = sound
        clock = FakeClock(0.0)
        sink = SoundSink(
            sound_path=_DEFAULT_ALARM,
            cooldown_seconds=5.0, clock=clock,
            ramp_seconds=0.0,
        )
        sink.notify(_event())
        sink.on_recovery(0)
        sound.play.reset_mock()
        clock.now = 10.0
        sink.notify(_event())
        sound.play.assert_called_once()


class TestValidation:
    def test_invalid_volumes(self):
        with pytest.raises(ValueError):
            SoundSink(Path("x"), start_volume=2.0)
        with pytest.raises(ValueError):
            SoundSink(Path("x"), peak_volume=-0.1)

    def test_start_above_peak_rejected(self):
        with pytest.raises(ValueError):
            SoundSink(Path("x"), start_volume=0.8, peak_volume=0.5)

    def test_negative_ramp_rejected(self):
        with pytest.raises(ValueError):
            SoundSink(Path("x"), ramp_seconds=-1)

    def test_negative_cooldown_rejected(self):
        with pytest.raises(ValueError):
            SoundSink(Path("x"), cooldown_seconds=-1)
