from pathlib import Path

import cv2
import numpy as np
import pytest

from driver_fatigue.application.ports import VideoSourcePort
from driver_fatigue.application.use_cases.monitor_driver import MonitorDriverUseCase
from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.domain.entities import Frame
from driver_fatigue.interfaces.config.settings import AppSettings


class FramesFromFile(VideoSourcePort):
    def __init__(self, path: Path, max_frames: int):
        self._cap = cv2.VideoCapture(str(path))
        self._max = max_frames
        self._i = 0
        self._released = False

    def read(self) -> Frame | None:
        if self._i >= self._max:
            return None
        ok, img = self._cap.read()
        if not ok:
            return None
        frame = Frame(image=img, timestamp=float(self._i), index=self._i)
        self._i += 1
        return frame

    def release(self) -> None:
        if not self._released:
            self._cap.release()
            self._released = True


@pytest.mark.timeout(30)
def test_pipeline_processes_test_video_headless(test_video_path):
    settings = AppSettings(headless=True)
    uc: MonitorDriverUseCase = build_monitor_use_case(
        settings=settings,
        source_override=FramesFromFile(test_video_path, max_frames=20),
        sound_override="disabled",
    )
    uc.run()
