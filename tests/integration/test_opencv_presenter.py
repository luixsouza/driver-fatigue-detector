from unittest.mock import patch

import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.rendering_theme import RenderingTheme
from driver_fatigue.infrastructure.presenters.opencv_window import OpenCvWindowPresenter
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer


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


class TestOpenCvWindowPresenter:
    @patch("driver_fatigue.infrastructure.presenters.opencv_window.cv2")
    def test_present_calls_imshow_with_rendered_frame(self, cv2_mock):
        cv2_mock.waitKey.return_value = 0
        renderer = FrameRenderer(theme=RenderingTheme())
        p = OpenCvWindowPresenter(renderer=renderer)
        p.present(_frame(), [_landmarks()], FatigueState.initial())
        assert cv2_mock.imshow.called
        call_args = cv2_mock.imshow.call_args
        assert call_args.args[0]
        assert isinstance(call_args.args[1], np.ndarray)

    @patch("driver_fatigue.infrastructure.presenters.opencv_window.cv2")
    def test_q_key_requests_stop(self, cv2_mock):
        cv2_mock.waitKey.return_value = ord('q')
        renderer = FrameRenderer(theme=RenderingTheme())
        p = OpenCvWindowPresenter(renderer=renderer)
        p.present(_frame(), [], FatigueState.initial())
        assert p.should_stop() is True

    @patch("driver_fatigue.infrastructure.presenters.opencv_window.cv2")
    def test_close_destroys_window(self, cv2_mock):
        cv2_mock.waitKey.return_value = 0
        renderer = FrameRenderer(theme=RenderingTheme())
        p = OpenCvWindowPresenter(renderer=renderer)
        p.close()
        assert cv2_mock.destroyWindow.called

    @patch("driver_fatigue.infrastructure.presenters.opencv_window.cv2")
    def test_close_is_idempotent(self, cv2_mock):
        cv2_mock.waitKey.return_value = 0
        renderer = FrameRenderer(theme=RenderingTheme())
        p = OpenCvWindowPresenter(renderer=renderer)
        p.close()
        p.close()
        assert cv2_mock.destroyWindow.call_count == 1
