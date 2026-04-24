from pathlib import Path

from driver_fatigue.interfaces.config.settings import AppSettings


class TestAppSettings:
    def test_defaults(self):
        s = AppSettings()
        assert s.source.kind == "webcam"
        assert s.source.index == 0
        assert s.thresholds.ear_threshold == 0.25
        assert s.alarm_sound_path.name == "alarm.wav"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("DRIVER_FATIGUE_SOURCE__INDEX", "2")
        monkeypatch.setenv("DRIVER_FATIGUE_THRESHOLDS__EAR_THRESHOLD", "0.30")
        s = AppSettings()
        assert s.source.index == 2
        assert s.thresholds.ear_threshold == 0.30

    def test_load_from_yaml(self, tmp_path):
        yaml = tmp_path / "conf.yaml"
        yaml.write_text(
            "thresholds:\n  ear_threshold: 0.22\n  mar_threshold: 0.55\n"
            "source:\n  kind: webcam\n  index: 1\n"
        )
        s = AppSettings.from_yaml(yaml)
        assert s.thresholds.ear_threshold == 0.22
        assert s.source.index == 1
