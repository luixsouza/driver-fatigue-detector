import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer
from driver_fatigue.infrastructure.rendering.theme import RenderingTheme


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


class TestFrameRenderer:
    def test_render_returns_numpy_array(self):
        r = FrameRenderer(theme=RenderingTheme())
        out = r.render(_frame(), [_landmarks()], FatigueState.initial())
        assert isinstance(out, np.ndarray)
        assert out.shape == (240, 320, 3)
        assert out.dtype == np.uint8

    def test_render_produces_non_black_output_with_landmarks(self):
        r = FrameRenderer(theme=RenderingTheme())
        state = FatigueState(
            ear=0.22, mar=0.35, consecutive_frames=3,
            is_fatigued=False, is_yawning=False, severity="warning",
        )
        out = r.render(_frame(), [_landmarks()], state)
        assert out.sum() > 0

    def test_render_no_faces_still_renders_hud(self):
        r = FrameRenderer(theme=RenderingTheme())
        out = r.render(_frame(), [], FatigueState.initial())
        assert out.sum() > 0

    def test_render_alert_adds_vignette(self):
        r_normal = FrameRenderer(theme=RenderingTheme())
        state_normal = FatigueState.initial()
        r_alert = FrameRenderer(theme=RenderingTheme())
        state_alert = FatigueState(
            ear=0.1, mar=0.1, consecutive_frames=30,
            is_fatigued=True, is_yawning=False, severity="alert",
        )
        out_normal = r_normal.render(_frame(), [_landmarks()], state_normal)
        out_alert = r_alert.render(_frame(), [_landmarks()], state_alert)
        assert out_alert[5, 5, 2] > out_normal[5, 5, 2]

    def test_render_does_not_mutate_input_frame(self):
        r = FrameRenderer(theme=RenderingTheme())
        frame = _frame()
        original = frame.image.copy()
        _ = r.render(frame, [_landmarks()], FatigueState.initial())
        assert np.array_equal(frame.image, original)
