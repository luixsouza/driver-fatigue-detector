from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SourceSettings(BaseModel):
    kind: Literal["webcam"] = "webcam"
    index: int = 0


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

    @classmethod
    def from_yaml(cls, path: Path) -> "AppSettings":
        data = yaml.safe_load(path.read_text())
        return cls(**(data or {}))
