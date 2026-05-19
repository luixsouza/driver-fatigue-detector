from pathlib import Path

import cv2
import pytest

from driver_fatigue.application.ports import VideoSourcePort
from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.config.settings import (
    AppSettings,
    RecordingSettings,
    SourceSettings,
)
from driver_fatigue.domain.entities import Frame


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
        frame = Frame(image=img, timestamp=float(self._i), index=self._i)
        self._i += 1
        return frame

    def release(self):
        if not self._released:
            self._cap.release()
            self._released = True


@pytest.mark.timeout(30)
def test_pipeline_processes_test_video_headless(test_video_path):
    settings = AppSettings(headless=True, sinks=["log"])
    uc = build_monitor_use_case(
        settings=settings,
        source_override=FramesFromFile(test_video_path, max_frames=20),
        sound_override="disabled",
    )
    uc.run()


@pytest.mark.timeout(60)
def test_pipeline_records_mp4_with_overlay(test_video_path, tmp_path):
    out = tmp_path / "recorded.mp4"
    settings = AppSettings(
        headless=True,
        sinks=["log"],
        recording=RecordingSettings(path=out, fps=10),
    )
    uc = build_monitor_use_case(
        settings=settings,
        source_override=FramesFromFile(test_video_path, max_frames=15),
        sound_override="disabled",
    )
    uc.run()
    assert out.exists() and out.stat().st_size > 0
    cap = cv2.VideoCapture(str(out))
    try:
        count = 0
        while True:
            ok, _ = cap.read()
            if not ok:
                break
            count += 1
        assert count >= 15
    finally:
        cap.release()


@pytest.mark.timeout(120)
def test_pipeline_works_with_file_source_via_settings(test_video_path):
    settings = AppSettings(
        headless=True,
        sinks=["log"],
        source=SourceSettings(kind="file", path=test_video_path, loop=False),
    )
    uc = build_monitor_use_case(settings=settings, sound_override="disabled")
    uc.run()
