from unittest.mock import MagicMock, patch

from driver_fatigue.config.settings import _DEFAULT_ALARM
from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.sound import SoundSink


def _event():
    return FatigueEvent(
        timestamp=0.0,
        state=FatigueState.initial(),
        frame_index=0,
    )


class TestSoundSink:
    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_notify_starts_playback(self, pygame_mock):
        pygame_mock.mixer.Sound.return_value = MagicMock()
        sink = SoundSink(sound_path=_DEFAULT_ALARM)
        sink.notify(_event())
        assert pygame_mock.mixer.Sound.return_value.play.called

    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_on_recovery_stops_playback(self, pygame_mock):
        pygame_mock.mixer.Sound.return_value = MagicMock()
        sink = SoundSink(sound_path=_DEFAULT_ALARM)
        sink.notify(_event())
        sink.on_recovery(frame_index=10)
        assert pygame_mock.mixer.Sound.return_value.stop.called

    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_repeated_notify_does_not_restart(self, pygame_mock):
        pygame_mock.mixer.Sound.return_value = MagicMock()
        sink = SoundSink(sound_path=_DEFAULT_ALARM)
        sink.notify(_event())
        sink.notify(_event())
        assert pygame_mock.mixer.Sound.return_value.play.call_count == 1
