"""E2E: pipeline com ContextValidator suprimindo alarme."""
from pathlib import Path

import cv2
import pytest

from driver_fatigue.application.ports import VideoSourcePort
from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueEvent,
    FatigueState,
    Frame,
)
from driver_fatigue.domain.value_objects import ContextVerdict
from driver_fatigue.interfaces.config.settings import AppSettings


class FramesFromFile(VideoSourcePort):
    def __init__(self, path: Path, max_frames: int):
        self._cap = cv2.VideoCapture(str(path))
        self._max = max_frames
        self._i = 0
        self._released = False

    def read(self):
        if self._i >= self._max:
            return None
        ok, img = self._cap.read()
        if not ok:
            return None
        f = Frame(image=img, timestamp=float(self._i) / 30.0, index=self._i)
        self._i += 1
        return f

    def release(self):
        if not self._released:
            self._cap.release()
            self._released = True


class AlwaysReject:
    def __init__(self):
        self.calls = 0

    def confirm_drowsy(
        self, frame: Frame, landmarks: FaceLandmarks, state: FatigueState,
    ) -> ContextVerdict:
        self.calls += 1
        return ContextVerdict.reject("test always reject")


class CountingSink:
    def __init__(self):
        self.notifications: list[FatigueEvent] = []
        self.recoveries: list[int] = []

    def notify(self, event):
        self.notifications.append(event)

    def on_recovery(self, frame_index):
        self.recoveries.append(frame_index)


@pytest.mark.timeout(60)
def test_validator_can_suppress_alerts_in_real_pipeline(test_video_path):
    """Mesmo que a heurística entre em alert, o validator REJECT deve suprimir
    qualquer notificação ao sink. Garante a integração ponta-a-ponta."""
    settings = AppSettings(headless=True, sinks=[])  # sink injetado via override
    sink = CountingSink()

    uc = build_monitor_use_case(
        settings=settings,
        source_override=FramesFromFile(test_video_path, max_frames=120),
        sound_override="disabled",
        validator_override=AlwaysReject(),
    )
    uc._sink = sink  # acessa atributo direto: simples e consistente com testes da Fase 2
    uc.run()
    assert sink.notifications == []
