import numpy as np
import pytest

from driver_fatigue.domain.entities import Point
from driver_fatigue.infrastructure.rendering.curves import catmull_rom_closed


class TestCatmullRomClosed:
    def test_interpolates_more_points_than_input(self):
        pts = [Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)]
        out = catmull_rom_closed(pts, steps_per_segment=10)
        assert len(out) > len(pts)
        assert len(out) == len(pts) * 10

    def test_returns_float32_array_shape_N_2(self):
        pts = [Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)]
        out = catmull_rom_closed(pts, steps_per_segment=5)
        assert out.dtype == np.float32
        assert out.shape[1] == 2

    def test_passes_through_input_points(self):
        pts = [Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)]
        out = catmull_rom_closed(pts, steps_per_segment=10)
        for p in pts:
            d = np.min(np.linalg.norm(out - np.array([p.x, p.y]), axis=1))
            assert d < 1e-4

    def test_steps_per_segment_zero_returns_just_input(self):
        pts = [Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)]
        out = catmull_rom_closed(pts, steps_per_segment=0)
        assert len(out) == len(pts)

    def test_requires_at_least_four_points(self):
        with pytest.raises(ValueError):
            catmull_rom_closed([Point(0, 0), Point(1, 1), Point(2, 0)], steps_per_segment=5)
