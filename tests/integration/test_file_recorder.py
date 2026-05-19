from pathlib import Path

import cv2
import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.infrastructure.rendering.theme import RenderingTheme
from driver_fatigue.infrastructure.presenters.file_recorder import FileRecorderPresenter
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer


def _pts(n, scale=30):
    return tuple(Point(x=float(i * scale / n + 5), y=float(i * scale / n + 5)) for i in range(n))


def _landmarks():
    return FaceLandmarks(
        left_eye_contour=_pts(6), right_eye_contour=_pts(6),
        left_iris=None, right_iris=None,
        mouth_outer=_pts(12), mouth_inner=_pts(8),
        face_oval=_pts(36, scale=100),
    )


class TestFileRecorderPresenter:
    def test_records_frames_to_mp4(self, tmp_path: Path):
        out = tmp_path / "rec.mp4"
        renderer = FrameRenderer(theme=RenderingTheme(glow_enabled=False))
        p = FileRecorderPresenter(renderer=renderer, output_path=out, fps=10)
        try:
            for i in range(5):
                frame = Frame(
                    image=np.zeros((120, 160, 3), dtype=np.uint8),
                    timestamp=float(i), index=i,
                )
                p.present(frame, [_landmarks()], FatigueState.initial())
        finally:
            p.close()

        assert out.exists()
        cap = cv2.VideoCapture(str(out))
        try:
            count = 0
            while True:
                ok, _ = cap.read()
                if not ok:
                    break
                count += 1
            assert count >= 5
        finally:
            cap.release()

    def test_close_before_present_does_nothing(self, tmp_path: Path):
        out = tmp_path / "empty.mp4"
        renderer = FrameRenderer(theme=RenderingTheme())
        p = FileRecorderPresenter(renderer=renderer, output_path=out, fps=10)
        p.close()
        assert not out.exists()

    def test_should_stop_always_false(self, tmp_path: Path):
        renderer = FrameRenderer(theme=RenderingTheme())
        p = FileRecorderPresenter(
            renderer=renderer, output_path=tmp_path / "x.mp4", fps=10,
        )
        assert p.should_stop() is False
        p.close()
