import numpy as np
import pytest

from driver_fatigue.domain.entities import Frame, Point


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
