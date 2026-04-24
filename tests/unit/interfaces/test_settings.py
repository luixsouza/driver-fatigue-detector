from pathlib import Path

import pytest
from pydantic import ValidationError

from driver_fatigue.interfaces.config.settings import AppSettings


class TestAppSettings:
    def test_defaults(self):
        s = AppSettings()
        assert s.source.kind == "webcam"
        assert s.source.index == 0
        assert s.thresholds.ear_threshold == 0.25
        assert s.alarm_sound_path.name == "alarm.wav"
        assert s.sinks == ["sound", "log"]
        assert s.recording.path is None

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("DRIVER_FATIGUE_SOURCE__INDEX", "2")
        monkeypatch.setenv("DRIVER_FATIGUE_THRESHOLDS__EAR_THRESHOLD", "0.30")
        s = AppSettings()
        assert s.source.index == 2
        assert s.thresholds.ear_threshold == 0.30

    def test_rtsp_requires_url(self):
        with pytest.raises(ValidationError):
            AppSettings(source={"kind": "rtsp"})

    def test_file_requires_path(self):
        with pytest.raises(ValidationError):
            AppSettings(source={"kind": "file"})

    def test_http_sink_requires_config(self):
        with pytest.raises(ValidationError):
            AppSettings(sinks=["http"])

    def test_mqtt_sink_requires_config(self):
        with pytest.raises(ValidationError):
            AppSettings(sinks=["mqtt"])

    def test_valid_rtsp_config(self):
        s = AppSettings(source={"kind": "rtsp", "url": "rtsp://fake/stream"})
        assert s.source.kind == "rtsp"
        assert s.source.url == "rtsp://fake/stream"

    def test_valid_http_sink_config(self):
        s = AppSettings(
            sinks=["http"],
            http_webhook={"url": "https://hook.x/events"},
        )
        assert s.http_webhook.url == "https://hook.x/events"

    def test_load_from_yaml(self, tmp_path):
        yaml = tmp_path / "conf.yaml"
        yaml.write_text(
            "source:\n  kind: file\n  path: assets/test.mp4\n"
            "sinks: [log]\n"
            "recording:\n  path: out.mp4\n  fps: 24\n"
        )
        s = AppSettings.from_yaml(yaml)
        assert s.source.kind == "file"
        assert s.source.path == Path("assets/test.mp4")
        assert s.sinks == ["log"]
        assert s.recording.path == Path("out.mp4")
        assert s.recording.fps == 24
