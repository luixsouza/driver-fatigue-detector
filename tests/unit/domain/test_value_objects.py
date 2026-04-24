import pytest

from driver_fatigue.domain.value_objects import FatigueThresholds


class TestFatigueThresholds:
    def test_defaults_match_original_code(self):
        t = FatigueThresholds()
        assert t.ear_threshold == 0.25
        assert t.mar_threshold == 0.60
        assert t.consecutive_frames == 20

    def test_warning_ratio_default(self):
        t = FatigueThresholds()
        assert t.warning_ratio == 0.85

    def test_is_frozen(self):
        t = FatigueThresholds()
        with pytest.raises((AttributeError, Exception)):
            t.ear_threshold = 0.9

    def test_rejects_invalid_warning_ratio(self):
        with pytest.raises(ValueError):
            FatigueThresholds(warning_ratio=1.5)

    def test_rejects_negative_consecutive_frames(self):
        with pytest.raises(ValueError):
            FatigueThresholds(consecutive_frames=-1)
