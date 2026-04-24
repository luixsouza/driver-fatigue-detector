from unittest.mock import MagicMock, patch

import numpy as np
import pytest


def _fake_cap(frames_before_fail: int = 3, then_succeed: bool = False):
    cap = MagicMock()
    cap.isOpened.return_value = True
    seq = []
    for _ in range(frames_before_fail):
        seq.append((True, np.zeros((2, 2, 3), dtype=np.uint8)))
    seq.append((False, None))
    if then_succeed:
        seq.append((True, np.zeros((2, 2, 3), dtype=np.uint8)))
    cap.read.side_effect = seq + [(False, None)]
    return cap


class TestRtspVideoSource:
    @patch("driver_fatigue.infrastructure.video_sources.rtsp.cv2")
    @patch("driver_fatigue.infrastructure.video_sources.rtsp.time.sleep")
    def test_reads_frames_until_exhaustion(self, sleep_mock, cv2_mock):
        from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource

        cv2_mock.VideoCapture.return_value = _fake_cap(frames_before_fail=3)
        src = RtspVideoSource(url="rtsp://fake")
        frames = []
        while True:
            f = src.read()
            if f is None:
                break
            frames.append(f)
        assert len(frames) == 3

    @patch("driver_fatigue.infrastructure.video_sources.rtsp.cv2")
    @patch("driver_fatigue.infrastructure.video_sources.rtsp.time.sleep")
    def test_reconnects_on_failure(self, sleep_mock, cv2_mock):
        from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource

        first_cap = _fake_cap(frames_before_fail=2, then_succeed=False)
        reconnect_cap = _fake_cap(frames_before_fail=1, then_succeed=False)
        cv2_mock.VideoCapture.side_effect = [first_cap, reconnect_cap, reconnect_cap, reconnect_cap]

        src = RtspVideoSource(url="rtsp://fake", reconnect_attempts=2)
        count = 0
        while True:
            f = src.read()
            if f is None:
                break
            count += 1
            if count > 100:
                break
        assert count >= 2
        assert cv2_mock.VideoCapture.call_count >= 2

    @patch("driver_fatigue.infrastructure.video_sources.rtsp.cv2")
    @patch("driver_fatigue.infrastructure.video_sources.rtsp.time.sleep")
    def test_release_is_idempotent(self, sleep_mock, cv2_mock):
        from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource

        cv2_mock.VideoCapture.return_value = _fake_cap(frames_before_fail=0)
        src = RtspVideoSource(url="rtsp://fake")
        src.release()
        src.release()

    @patch("driver_fatigue.infrastructure.video_sources.rtsp.cv2")
    def test_raises_when_cant_open(self, cv2_mock):
        from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource

        bad = MagicMock()
        bad.isOpened.return_value = False
        cv2_mock.VideoCapture.return_value = bad
        with pytest.raises(RuntimeError):
            RtspVideoSource(url="rtsp://unreachable")
