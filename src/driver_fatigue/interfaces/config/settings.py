from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SourceSettings(BaseModel):
    kind: Literal["webcam", "rtsp", "file"] = "webcam"
    index: int = 0
    url: str | None = None
    path: Path | None = None
    loop: bool = False

    @model_validator(mode="after")
    def _check_fields_for_kind(self) -> "SourceSettings":
        if self.kind == "rtsp" and not self.url:
            raise ValueError("source.url é obrigatório quando kind='rtsp'")
        if self.kind == "file" and self.path is None:
            raise ValueError("source.path é obrigatório quando kind='file'")
        return self


class ThresholdsSettings(BaseModel):
    ear_threshold: float = 0.25
    mar_threshold: float = 0.60
    consecutive_frames: int = 20
    warning_ratio: float = 0.85
    recovery_frames: int = 10
    min_alert_duration_frames: int = 5
    alarm_cooldown_seconds: float = 5.0
    yawn_window_frames: int = 45
    yawn_stability_max: float = 0.04


class CalibrationSettingsModel(BaseModel):
    enabled: bool = True
    warmup_frames: int = 60
    ear_close_ratio: float = 0.75
    mar_open_zscore: float = 2.5


class FrameQualitySettings(BaseModel):
    enabled: bool = True
    min_face_confidence: float = 0.5
    min_face_area_ratio: float = 0.05
    max_head_yaw_deg: float = 35.0
    max_head_pitch_deg: float = 25.0


class SoundSinkSettings(BaseModel):
    start_volume: float = 0.4
    peak_volume: float = 1.0
    ramp_seconds: float = 1.5
    cooldown_seconds: float = 2.0


class ContextValidatorSettings(BaseModel):
    kind: Literal["noop", "eye_state"] = "noop"
    min_confidence: float = 0.6
    fail_safe_on_error: Literal["alarm", "suppress"] = "alarm"
    perclos_window_seconds: float = 60.0
    perclos_threshold: float = 0.4
    eye_state_model_path: Path | None = None


class DashboardStreamSettings(BaseModel):
    enabled: bool = False
    push_url: str = "http://127.0.0.1:8000/api/video/push"
    jpeg_quality: int = 88
    max_fps: float = 30.0


class ThemeSettings(BaseModel):
    glow_enabled: bool = True
    show_hud: bool = True
    show_face_oval: bool = True
    smoothing_steps: int = 20
    overlay_alpha: float = 0.35


class HttpWebhookSettings(BaseModel):
    url: str
    bearer_token: str | None = None
    timeout_seconds: float = 3.0


class MqttSettings(BaseModel):
    broker: str
    port: int = 1883
    topic: str = "driver_fatigue/events"
    username: str | None = None
    password: str | None = None


class RecordingSettings(BaseModel):
    path: Path | None = None
    fps: int = 30
    codec: str = "mp4v"


class JsonlSinkSettings(BaseModel):
    path: Path = Path("events.jsonl")


class WebSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    api_key: str | None = None


SinkName = Literal["sound", "log", "http", "mqtt", "jsonl"]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DRIVER_FATIGUE_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    source: SourceSettings = Field(default_factory=SourceSettings)
    thresholds: ThresholdsSettings = Field(default_factory=ThresholdsSettings)
    calibration: CalibrationSettingsModel = Field(default_factory=CalibrationSettingsModel)
    frame_quality: FrameQualitySettings = Field(default_factory=FrameQualitySettings)
    theme: ThemeSettings = Field(default_factory=ThemeSettings)
    alarm_sound_path: Path = Path("audio/alarm.wav")
    sound_sink: SoundSinkSettings = Field(default_factory=SoundSinkSettings)
    headless: bool = False

    sinks: list[SinkName] = Field(default_factory=lambda: ["sound", "log"])
    http_webhook: HttpWebhookSettings | None = None
    mqtt: MqttSettings | None = None
    recording: RecordingSettings = Field(default_factory=RecordingSettings)
    context_validator: ContextValidatorSettings = Field(default_factory=ContextValidatorSettings)
    dashboard_stream: DashboardStreamSettings = Field(default_factory=DashboardStreamSettings)
    jsonl: JsonlSinkSettings = Field(default_factory=JsonlSinkSettings)
    web: WebSettings = Field(default_factory=WebSettings)

    @model_validator(mode="after")
    def _check_sink_configs(self) -> "AppSettings":
        if "http" in self.sinks and self.http_webhook is None:
            raise ValueError("sinks inclui 'http' mas http_webhook não foi definido")
        if "mqtt" in self.sinks and self.mqtt is None:
            raise ValueError("sinks inclui 'mqtt' mas mqtt não foi definido")
        return self

    @classmethod
    def from_yaml(cls, path: Path) -> "AppSettings":
        data = yaml.safe_load(path.read_text())
        return cls(**(data or {}))
