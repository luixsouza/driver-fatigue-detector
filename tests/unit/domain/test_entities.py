import numpy as np
import pytest

from driver_fatigue.domain.entities import Frame, Point
from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueEvent,
    FatigueState,
    Severity,
)


class TestPoint:
    def test_point_has_x_and_y(self):
        p = Point(x=1.5, y=2.5)
        assert p.x == 1.5
        assert p.y == 2.5

    def test_point_is_frozen(self):
        p = Point(x=1.0, y=2.0)
        with pytest.raises((AttributeError, Exception)):
            p.x = 99.0


class TestFrame:
    def test_frame_stores_image_timestamp_and_index(self):
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        f = Frame(image=img, timestamp=1.5, index=42)
        assert f.image is img
        assert f.timestamp == 1.5
        assert f.index == 42

    def test_frame_is_frozen(self):
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        f = Frame(image=img, timestamp=0.0, index=0)
        with pytest.raises((AttributeError, Exception)):
            f.index = 99

    def test_frame_has_identity_equality(self):
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        f1 = Frame(image=img, timestamp=0.0, index=0)
        f2 = Frame(image=img, timestamp=0.0, index=0)
        assert f1 is not f2
        assert f1 != f2  # eq=False → fallback to identity


def _pts(n: int) -> tuple:
    return tuple(Point(x=float(i), y=float(i)) for i in range(n))


class TestFaceLandmarks:
    def test_all_required_regions_present(self):
        lm = FaceLandmarks(
            left_eye_contour=_pts(6),
            right_eye_contour=_pts(6),
            left_iris=_pts(5),
            right_iris=_pts(5),
            mouth_outer=_pts(12),
            mouth_inner=_pts(8),
            face_oval=_pts(36),
        )
        assert len(lm.left_eye_contour) == 6
        assert lm.left_iris is not None

    def test_iris_can_be_none(self):
        lm = FaceLandmarks(
            left_eye_contour=_pts(6),
            right_eye_contour=_pts(6),
            left_iris=None,
            right_iris=None,
            mouth_outer=_pts(12),
            mouth_inner=_pts(8),
            face_oval=_pts(36),
        )
        assert lm.left_iris is None
        assert lm.right_iris is None


class TestFatigueState:
    def test_initial_state_is_normal(self):
        s = FatigueState.initial()
        assert s.ear == 0.0
        assert s.mar == 0.0
        assert s.consecutive_frames == 0
        assert s.is_fatigued is False
        assert s.is_yawning is False
        assert s.severity == "normal"

    def test_state_is_frozen(self):
        s = FatigueState.initial()
        with pytest.raises((AttributeError, Exception)):
            s.ear = 0.9


class TestFatigueEvent:
    def test_event_has_timestamp_state_and_frame_index(self):
        s = FatigueState.initial()
        e = FatigueEvent(timestamp=1.5, state=s, frame_index=10)
        assert e.timestamp == 1.5
        assert e.state is s
        assert e.frame_index == 10
