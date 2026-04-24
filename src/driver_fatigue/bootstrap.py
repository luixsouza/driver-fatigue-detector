from __future__ import annotations

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
from driver_fatigue.infrastructure.alert_sinks.log import LogSink
from driver_fatigue.infrastructure.alert_sinks.sound import SoundSink
from driver_fatigue.infrastructure.detectors.mediapipe_detector import MediapipeFaceDetector
from driver_fatigue.infrastructure.presenters.opencv_window import OpenCvWindowPresenter
from driver_fatigue.infrastructure.video_sources.webcam import WebcamVideoSource
from driver_fatigue.interfaces.config.settings import AppSettings


class _CompositeSink:
    def __init__(self, *sinks: AlertSinkPort) -> None:
        self._sinks = sinks

    def notify(self, event) -> None:
        for s in self._sinks:
            try:
                s.notify(event)
            except Exception:
                import logging
                logging.getLogger("driver_fatigue").exception(
                    "sink %s falhou em notify", type(s).__name__,
                )

    def on_recovery(self, frame_index: int) -> None:
        for s in self._sinks:
            try:
                s.on_recovery(frame_index)
            except Exception:
                import logging
                logging.getLogger("driver_fatigue").exception(
                    "sink %s falhou em on_recovery", type(s).__name__,
                )


def _build_source(settings: AppSettings) -> VideoSourcePort:
    if settings.source.kind == "webcam":
        return WebcamVideoSource(device_index=settings.source.index)
    raise ValueError(f"source.kind {settings.source.kind!r} não suportado na Fase 1")


def _build_presenter(settings: AppSettings) -> FramePresenterPort:
    theme = RenderingTheme(
        glow_enabled=settings.theme.glow_enabled,
        show_hud=settings.theme.show_hud,
        show_face_oval=settings.theme.show_face_oval,
        smoothing_steps=settings.theme.smoothing_steps,
        overlay_alpha=settings.theme.overlay_alpha,
    )
    return OpenCvWindowPresenter(theme=theme, headless=settings.headless)


def _build_sink(
    settings: AppSettings,
    sound_override: Literal["disabled"] | None = None,
) -> AlertSinkPort:
    log_sink = LogSink()
    if sound_override == "disabled":
        return log_sink
    try:
        sound_sink = SoundSink(sound_path=settings.alarm_sound_path)
        return _CompositeSink(sound_sink, log_sink)
    except Exception:
        import logging
        logging.getLogger("driver_fatigue").warning(
            "SoundSink indisponível, usando somente LogSink",
        )
        return log_sink


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
    sink = _build_sink(settings, sound_override=sound_override)
    presenter = _build_presenter(settings)
    return MonitorDriverUseCase(
        source=source, detect=detect, sink=sink, presenter=presenter,
    )
