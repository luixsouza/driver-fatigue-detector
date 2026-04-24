import numpy as np

from driver_fatigue.infrastructure.rendering.glow import apply_glow
from driver_fatigue.infrastructure.rendering.hud import draw_hud
from driver_fatigue.infrastructure.rendering.overlay import draw_filled_overlay


def _blank(h=100, w=200):
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestDrawFilledOverlay:
    def test_paints_region(self):
        img = _blank()
        polygon = np.array([[50, 30], [100, 30], [100, 60], [50, 60]], dtype=np.int32)
        out = draw_filled_overlay(img, polygon, color=(0, 255, 0), alpha=0.5)
        assert out[45, 75, 1] > 0

    def test_does_not_modify_input(self):
        img = _blank()
        original = img.copy()
        polygon = np.array([[10, 10], [20, 10], [20, 20], [10, 20]], dtype=np.int32)
        _ = draw_filled_overlay(img, polygon, color=(255, 0, 0), alpha=0.5)
        assert np.array_equal(img, original)


class TestApplyGlow:
    def test_glow_increases_brightness_around_line(self):
        img = _blank()
        img[50, 100:110] = (255, 255, 255)
        out = apply_glow(img, sigma=5)
        assert out[52, 105, 0] > 0


class TestDrawHud:
    def test_hud_writes_pixels_in_bottom_region(self):
        img = _blank(h=300, w=400)
        out = draw_hud(
            img,
            ear=0.22, mar=0.35, consecutive=8, fps=29.5, severity="warning",
            max_consecutive=20,
        )
        assert out[250:, :, :].sum() > 0
