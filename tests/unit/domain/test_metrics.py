
import pytest

from driver_fatigue.domain.entities import Point
from driver_fatigue.domain.metrics import eye_aspect_ratio, mouth_aspect_ratio


def _eye(open_ratio: float) -> tuple[Point, ...]:
    """Olho sintético: p0 e p3 são cantos (largura=1.0),
    p1,p2 em cima e p5,p4 embaixo separados por open_ratio."""
    h = open_ratio / 2
    return (
        Point(x=0.0, y=0.0),
        Point(x=0.3, y=-h),
        Point(x=0.7, y=-h),
        Point(x=1.0, y=0.0),
        Point(x=0.7, y=h),
        Point(x=0.3, y=h),
    )


class TestEyeAspectRatio:
    def test_fully_open_eye(self):
        eye = _eye(open_ratio=0.4)
        assert eye_aspect_ratio(eye) == pytest.approx(0.4, abs=1e-6)

    def test_closed_eye(self):
        eye = _eye(open_ratio=0.0)
        assert eye_aspect_ratio(eye) == pytest.approx(0.0, abs=1e-6)

    def test_standard_threshold_boundary(self):
        eye = _eye(open_ratio=0.25)
        assert eye_aspect_ratio(eye) == pytest.approx(0.25, abs=1e-6)

    def test_raises_on_wrong_number_of_points(self):
        pts = tuple(Point(x=float(i), y=0.0) for i in range(5))
        with pytest.raises(ValueError):
            eye_aspect_ratio(pts)

    def test_raises_on_zero_width(self):
        pts = (
            Point(0.0, 0.0), Point(0.0, 0.0), Point(0.0, 0.0),
            Point(0.0, 0.0), Point(0.0, 0.0), Point(0.0, 0.0),
        )
        with pytest.raises(ValueError):
            eye_aspect_ratio(pts)


def _mouth(open_ratio: float) -> tuple[Point, ...]:
    """Boca sintética com 12 pontos. Largura=1.0, abertura=open_ratio."""
    h = open_ratio / 2
    return (
        Point(0.0, 0.0),
        Point(0.15, -h),
        Point(0.35, -h),
        Point(0.5, -h),
        Point(0.65, -h),
        Point(0.85, -h),
        Point(1.0, 0.0),
        Point(0.85, h),
        Point(0.65, h),
        Point(0.5, h),
        Point(0.35, h),
        Point(0.15, h),
    )


class TestMouthAspectRatio:
    def test_closed_mouth(self):
        m = _mouth(open_ratio=0.0)
        assert mouth_aspect_ratio(m) == pytest.approx(0.0, abs=1e-6)

    def test_open_mouth(self):
        m = _mouth(open_ratio=0.6)
        assert mouth_aspect_ratio(m) == pytest.approx(0.6, abs=1e-6)

    def test_raises_on_wrong_number_of_points(self):
        pts = tuple(Point(x=float(i), y=0.0) for i in range(11))
        with pytest.raises(ValueError):
            mouth_aspect_ratio(pts)

    def test_raises_on_zero_width(self):
        pts = tuple(Point(0.0, 0.0) for _ in range(12))
        with pytest.raises(ValueError):
            mouth_aspect_ratio(pts)
