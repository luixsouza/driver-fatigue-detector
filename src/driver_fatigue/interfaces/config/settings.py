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


SinkName = Literal["sound", "log", "http", "mqtt"]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DRIVER_FATIGUE_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    source: SourceSettings = Field(default_factory=SourceSettings)
    thresholds: ThresholdsSettings = Field(default_factory=ThresholdsSettings)
    theme: ThemeSettings = Field(default_factory=ThemeSettings)
    alarm_sound_path: Path = Path("audio/alarm.wav")
    headless: bool = False

    sinks: list[SinkName] = Field(default_factory=lambda: ["sound", "log"])
    http_webhook: HttpWebhookSettings | None = None
    mqtt: MqttSettings | None = None
    recording: RecordingSettings = Field(default_factory=RecordingSettings)

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
