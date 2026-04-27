import pytest

from driver_fatigue.domain.entities import FaceLandmarks, Point
from driver_fatigue.domain.quality import (
    estimate_face_area_ratio,
    estimate_pitch_deg,
    estimate_quality,
    estimate_yaw_deg,
)
from driver_fatigue.domain.value_objects import FrameQualityPolicy


def _eye(width: float, x_offset: float = 0.0):
    return tuple(
        Point(x_offset + width * x, 0.0)
        for x in (0.0, 0.3, 0.7, 1.0, 0.7, 0.3)
    )


def _square_oval(side: float = 1.0, top_left: tuple = (0.0, 0.0)):
    x0, y0 = top_left
    pts: list[Point] = []
    for i in range(36):
        # 4 lados de 9 pontos
        if i < 9:
            pts.append(Point(x0 + side * (i / 9), y0))
        elif i < 18:
            pts.append(Point(x0 + side, y0 + side * ((i - 9) / 9)))
        elif i < 27:
            pts.append(Point(x0 + side - side * ((i - 18) / 9), y0 + side))
        else:
            pts.append(Point(x0, y0 + side - side * ((i - 27) / 9)))
    return tuple(pts)


def _landmarks(left_w=1.0, right_w=1.0, oval_size=2.0, oval_origin=(0.0, 0.0)):
    return FaceLandmarks(
        left_eye_contour=_eye(left_w, x_offset=oval_origin[0] + 0.2),
        right_eye_contour=_eye(right_w, x_offset=oval_origin[0] + 1.0),
        left_iris=None, right_iris=None,
        mouth_outer=tuple(Point(0, 0) for _ in range(12)),
        mouth_inner=tuple(Point(0, 0) for _ in range(8)),
        face_oval=_square_oval(oval_size, oval_origin),
    )


class TestEstimateYaw:
    def test_symmetric_eyes_zero_yaw(self):
        lm = _landmarks(left_w=1.0, right_w=1.0)
        assert abs(estimate_yaw_deg(lm)) < 1e-6

    def test_asymmetric_eyes_nonzero_yaw(self):
        lm = _landmarks(left_w=1.0, right_w=0.5)
        yaw = estimate_yaw_deg(lm)
        assert yaw > 10
        assert yaw <= 90


class TestEstimatePitch:
    def test_eyes_at_center_zero_pitch(self):
        lm = _landmarks(oval_size=2.0, oval_origin=(0.0, -1.0))
        # eye_center_y = 0; oval_center_y = 0
        assert abs(estimate_pitch_deg(lm)) < 1e-6


class TestFaceAreaRatio:
    def test_full_face_ratio(self):
        lm = _landmarks(oval_size=10.0, oval_origin=(0.0, 0.0))
        ratio = estimate_face_area_ratio(lm, frame_width=20, frame_height=20)
        # bbox 10x10 / frame 400 = 0.25
        assert abs(ratio - 0.25) < 1e-6

    def test_zero_frame_size_returns_zero(self):
        lm = _landmarks()
        assert estimate_face_area_ratio(lm, 0, 0) == 0.0


class TestPolicy:
    def test_production_policy_blocks_high_yaw(self):
        lm = _landmarks(left_w=1.0, right_w=0.2, oval_size=10.0)
        q = estimate_quality(lm, 20, 20, FrameQualityPolicy.production())
        assert not q.trustworthy
        assert "yaw" in q.reason

    def test_production_policy_blocks_small_face(self):
        lm = _landmarks(oval_size=1.0, oval_origin=(0.0, 0.0))  # 1x1 in 100x100
        q = estimate_quality(lm, 100, 100, FrameQualityPolicy.production())
        assert not q.trustworthy
        assert "small" in q.reason

    def test_production_policy_passes_good_frame(self):
        lm = _landmarks(left_w=1.0, right_w=1.0, oval_size=10.0, oval_origin=(0.0, -5.0))
        q = estimate_quality(lm, 20, 20, FrameQualityPolicy.production())
        assert q.trustworthy
        assert q.reason == ""


class TestDegenerateInputs:
    def test_zero_width_eyes_returns_zero_yaw(self):
        from driver_fatigue.domain.entities import FaceLandmarks
        # eye contour with all points at same place → width = 0
        zero_eye = tuple(Point(0.0, 0.0) for _ in range(6))
        lm = FaceLandmarks(
            left_eye_contour=zero_eye, right_eye_contour=zero_eye,
            left_iris=None, right_iris=None,
            mouth_outer=tuple(Point(0, 0) for _ in range(12)),
            mouth_inner=tuple(Point(0, 0) for _ in range(8)),
            face_oval=_square_oval(2.0),
        )
        assert estimate_yaw_deg(lm) == 0.0

    def test_short_eye_contour_yaw_zero(self):
        from driver_fatigue.domain.entities import FaceLandmarks
        short_eye = tuple(Point(0.0, 0.0) for _ in range(2))
        lm = FaceLandmarks(
            left_eye_contour=short_eye, right_eye_contour=short_eye,
            left_iris=None, right_iris=None,
            mouth_outer=tuple(Point(0, 0) for _ in range(12)),
            mouth_inner=tuple(Point(0, 0) for _ in range(8)),
            face_oval=_square_oval(2.0),
        )
        assert estimate_yaw_deg(lm) == 0.0

    def test_no_oval_returns_zero_pitch(self):
        from driver_fatigue.domain.entities import FaceLandmarks
        eye = _eye(1.0)
        lm = FaceLandmarks(
            left_eye_contour=eye, right_eye_contour=eye,
            left_iris=None, right_iris=None,
            mouth_outer=tuple(Point(0, 0) for _ in range(12)),
            mouth_inner=tuple(Point(0, 0) for _ in range(8)),
            face_oval=(),
        )
        assert estimate_pitch_deg(lm) == 0.0

    def test_zero_height_oval_returns_zero_pitch(self):
        from driver_fatigue.domain.entities import FaceLandmarks
        eye = _eye(1.0)
        flat_oval = tuple(Point(float(i), 0.0) for i in range(36))
        lm = FaceLandmarks(
            left_eye_contour=eye, right_eye_contour=eye,
            left_iris=None, right_iris=None,
            mouth_outer=tuple(Point(0, 0) for _ in range(12)),
            mouth_inner=tuple(Point(0, 0) for _ in range(8)),
            face_oval=flat_oval,
        )
        assert estimate_pitch_deg(lm) == 0.0

    def test_no_oval_returns_zero_area(self):
        from driver_fatigue.domain.entities import FaceLandmarks
        eye = _eye(1.0)
        lm = FaceLandmarks(
            left_eye_contour=eye, right_eye_contour=eye,
            left_iris=None, right_iris=None,
            mouth_outer=tuple(Point(0, 0) for _ in range(12)),
            mouth_inner=tuple(Point(0, 0) for _ in range(8)),
            face_oval=(),
        )
        assert estimate_face_area_ratio(lm, 100, 100) == 0.0


class TestPolicyValidation:
    def test_invalid_min_face_confidence(self):
        with pytest.raises(ValueError):
            FrameQualityPolicy(min_face_confidence=2.0)

    def test_invalid_min_face_area(self):
        with pytest.raises(ValueError):
            FrameQualityPolicy(min_face_area_ratio=-0.1)

    def test_invalid_max_yaw(self):
        with pytest.raises(ValueError):
            FrameQualityPolicy(max_head_yaw_deg=-1)

    def test_invalid_max_pitch(self):
        with pytest.raises(ValueError):
            FrameQualityPolicy(max_head_pitch_deg=0)
