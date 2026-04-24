from __future__ import annotations

import logging
from typing import Literal

from driver_fatigue.application.ports import (
    AlertSinkPort,
    FramePresenterPort,
    VideoSourcePort,
)
from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.application.use_cases.monitor_driver import MonitorDriverUseCase
from driver_fatigue.domain.rendering_theme import RenderingTheme
from driver_fatigue.domain.value_objects import FatigueThresholds
from driver_fatigue.infrastructure.alert_sinks.composite import CompositeSink
from driver_fatigue.infrastructure.alert_sinks.http_webhook import HttpWebhookSink
from driver_fatigue.infrastructure.alert_sinks.log import LogSink
from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink
from driver_fatigue.infrastructure.alert_sinks.sound import SoundSink
from driver_fatigue.infrastructure.detectors.mediapipe_detector import MediapipeFaceDetector
from driver_fatigue.infrastructure.presenters.composite import CompositePresenter
from driver_fatigue.infrastructure.presenters.file_recorder import FileRecorderPresenter
from driver_fatigue.infrastructure.presenters.headless import HeadlessPresenter
from driver_fatigue.infrastructure.presenters.opencv_window import OpenCvWindowPresenter
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer
from driver_fatigue.infrastructure.video_sources.file import FileVideoSource
from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource
from driver_fatigue.infrastructure.video_sources.webcam import WebcamVideoSource
from driver_fatigue.interfaces.config.settings import AppSettings

_log = logging.getLogger("driver_fatigue.bootstrap")


def _build_source(settings: AppSettings) -> VideoSourcePort:
    kind = settings.source.kind
    if kind == "webcam":
        return WebcamVideoSource(device_index=settings.source.index)
    if kind == "rtsp":
        assert settings.source.url is not None
        return RtspVideoSource(url=settings.source.url)
    if kind == "file":
        assert settings.source.path is not None
        return FileVideoSource(path=settings.source.path, loop=settings.source.loop)
    raise ValueError(f"source.kind {kind!r} não suportado")


def _build_single_sink(
    name: str,
    settings: AppSettings,
    sound_override: Literal["disabled"] | None = None,
) -> AlertSinkPort | None:
    if name == "log":
        return LogSink()
    if name == "sound":
        if sound_override == "disabled":
            return None
        try:
            return SoundSink(sound_path=settings.alarm_sound_path)
        except Exception:
            _log.warning("SoundSink indisponivel, ignorando")
            return None
    if name == "http":
        cfg = settings.http_webhook
        assert cfg is not None
        return HttpWebhookSink(
            url=cfg.url, bearer_token=cfg.bearer_token,
            timeout_seconds=cfg.timeout_seconds,
        )
    if name == "mqtt":
        cfg = settings.mqtt
        assert cfg is not None
        return MqttSink(
            broker=cfg.broker, port=cfg.port, topic=cfg.topic,
            username=cfg.username, password=cfg.password,
        )
    raise ValueError(f"sink {name!r} desconhecido")


def _build_sinks(
    settings: AppSettings,
    sound_override: Literal["disabled"] | None = None,
) -> AlertSinkPort:
    resolved = []
    for name in settings.sinks:
        s = _build_single_sink(name, settings, sound_override)
        if s is not None:
            resolved.append(s)
    if not resolved:
        resolved.append(LogSink())
    return CompositeSink(*resolved)


def _build_renderer(settings: AppSettings) -> FrameRenderer:
    theme = RenderingTheme(
        glow_enabled=settings.theme.glow_enabled,
        show_hud=settings.theme.show_hud,
        show_face_oval=settings.theme.show_face_oval,
        smoothing_steps=settings.theme.smoothing_steps,
        overlay_alpha=settings.theme.overlay_alpha,
    )
    return FrameRenderer(theme=theme)


def _build_presenter(
    settings: AppSettings,
    renderer: FrameRenderer,
) -> FramePresenterPort:
    main = HeadlessPresenter() if settings.headless else OpenCvWindowPresenter(renderer=renderer)
    if settings.recording.path is None:
        return main
    recorder = FileRecorderPresenter(
        renderer=renderer,
        output_path=settings.recording.path,
        fps=settings.recording.fps,
        codec=settings.recording.codec,
    )
    return CompositePresenter(main, recorder)


def build_monitor_use_case(
    settings: AppSettings,
    source_override: VideoSourcePort | None = None,
    sound_override: Literal["disabled"] | None = None,
) -> MonitorDriverUseCase:
    source = source_override if source_override is not None else _build_source(settings)
    detector = MediapipeFaceDetector()
    thresholds = FatigueThresholds(
        ear_threshold=settings.thresholds.ear_threshold,
        mar_threshold=settings.thresholds.mar_threshold,
        consecutive_frames=settings.thresholds.consecutive_frames,
        warning_ratio=settings.thresholds.warning_ratio,
    )
    detect = DetectFatigueUseCase(detector=detector, thresholds=thresholds)
    sink = _build_sinks(settings, sound_override=sound_override)
    renderer = _build_renderer(settings)
    presenter = _build_presenter(settings, renderer)
    return MonitorDriverUseCase(
        source=source, detect=detect, sink=sink, presenter=presenter,
    )
