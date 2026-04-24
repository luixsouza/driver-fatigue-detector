import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.rendering_theme import RenderingTheme
from driver_fatigue.infrastructure.presenters.opencv_window import OpenCvWindowPresenter


def _pts(n, scale=50):
    return tuple(Point(x=float(i * scale / n + 10), y=float(i * scale / n + 10)) for i in range(n))


def _landmarks():
    return FaceLandmarks(
        left_eye_contour=_pts(6), right_eye_contour=_pts(6),
        left_iris=_pts(5), right_iris=_pts(5),
        mouth_outer=_pts(12), mouth_inner=_pts(8),
        face_oval=_pts(36, scale=200),
    )


def _frame():
    return Frame(image=np.zeros((240, 320, 3), dtype=np.uint8), timestamp=0.0, index=0)


class TestOpenCvWindowPresenterHeadless:
    def test_render_produces_non_black_output(self):
        p = OpenCvWindowPresenter(theme=RenderingTheme(), headless=True)
        state = FatigueState(
            ear=0.22, mar=0.35, consecutive_frames=3,
            is_fatigued=False, is_yawning=False, severity="warning",
        )
        p.present(_frame(), [_landmarks()], state)
        assert p.last_rendered is not None
        assert p.last_rendered.sum() > 0

    def test_no_faces_still_renders_hud(self):
        p = OpenCvWindowPresenter(theme=RenderingTheme(), headless=True)
        p.present(_frame(), [], FatigueState.initial())
        assert p.last_rendered is not None
        assert p.last_rendered.sum() > 0

    def test_should_stop_defaults_false_in_headless(self):
        p = OpenCvWindowPresenter(theme=RenderingTheme(), headless=True)
        assert p.should_stop() is False

    def test_close_is_idempotent(self):
        p = OpenCvWindowPresenter(theme=RenderingTheme(), headless=True)
        p.close()
        p.close()
