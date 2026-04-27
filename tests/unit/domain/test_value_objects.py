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

    def test_rejects_zero_ear_threshold(self):
        with pytest.raises(ValueError):
            FatigueThresholds(ear_threshold=0)

    def test_rejects_zero_mar_threshold(self):
        with pytest.raises(ValueError):
            FatigueThresholds(mar_threshold=0)

    def test_rejects_negative_recovery_frames(self):
        with pytest.raises(ValueError):
            FatigueThresholds(recovery_frames=-1)

    def test_rejects_negative_min_alert_duration(self):
        with pytest.raises(ValueError):
            FatigueThresholds(min_alert_duration_frames=-1)

    def test_rejects_negative_alarm_cooldown(self):
        with pytest.raises(ValueError):
            FatigueThresholds(alarm_cooldown_seconds=-1)

    def test_rejects_zero_yawn_window(self):
        with pytest.raises(ValueError):
            FatigueThresholds(yawn_window_frames=0)

    def test_rejects_negative_yawn_stability(self):
        with pytest.raises(ValueError):
            FatigueThresholds(yawn_stability_max=-0.01)


class TestCalibrationSettings:
    def test_rejects_negative_warmup(self):
        from driver_fatigue.domain.value_objects import CalibrationSettings
        with pytest.raises(ValueError):
            CalibrationSettings(warmup_frames=-1)

    def test_rejects_invalid_ear_close_ratio(self):
        from driver_fatigue.domain.value_objects import CalibrationSettings
        with pytest.raises(ValueError):
            CalibrationSettings(ear_close_ratio=0.0)
        with pytest.raises(ValueError):
            CalibrationSettings(ear_close_ratio=1.0)

    def test_rejects_zero_zscore(self):
        from driver_fatigue.domain.value_objects import CalibrationSettings
        with pytest.raises(ValueError):
            CalibrationSettings(mar_open_zscore=0)


class TestContextVerdict:
    def test_confirm_helper(self):
        from driver_fatigue.domain.value_objects import ContextVerdict
        v = ContextVerdict.confirm("ok")
        assert v.drowsy is True and v.confidence == 1.0 and v.reason == "ok"

    def test_reject_helper(self):
        from driver_fatigue.domain.value_objects import ContextVerdict
        v = ContextVerdict.reject("nope")
        assert v.drowsy is False and v.confidence == 1.0 and v.reason == "nope"


class TestFrameQualityFactories:
    def test_trusted_with_overrides(self):
        from driver_fatigue.domain.value_objects import FrameQuality
        q = FrameQuality.trusted(head_yaw_deg=10.0, face_area_ratio=0.2)
        assert q.trustworthy and q.head_yaw_deg == 10.0

    def test_untrusted_with_reason(self):
        from driver_fatigue.domain.value_objects import FrameQuality
        q = FrameQuality.untrusted("test")
        assert not q.trustworthy and q.reason == "test"
