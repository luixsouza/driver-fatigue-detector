import pytest

from driver_fatigue.domain.rendering_theme import RenderingTheme


class TestRenderingTheme:
    def test_defaults(self):
        t = RenderingTheme()
        assert t.color_normal == (255, 255, 0)
        assert t.color_warning == (0, 200, 255)
        assert t.color_alert == (50, 50, 255)
        assert t.overlay_alpha == 0.35
        assert t.glow_enabled is True
        assert t.show_hud is True
        assert t.smoothing_steps == 20

    def test_is_frozen(self):
        t = RenderingTheme()
        with pytest.raises((AttributeError, Exception)):
            t.show_hud = False

    def test_rejects_alpha_out_of_range(self):
        with pytest.raises(ValueError):
            RenderingTheme(overlay_alpha=1.5)

    def test_rejects_negative_smoothing(self):
        with pytest.raises(ValueError):
            RenderingTheme(smoothing_steps=-1)
