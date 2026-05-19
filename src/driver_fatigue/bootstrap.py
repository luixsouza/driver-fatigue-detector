from __future__ import annotations

import logging
from typing import Literal

from driver_fatigue.application.ports import (
    AlertSinkPort,
    ContextValidatorPort,
    FramePresenterPort,
    VideoSourcePort,
)
from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.application.use_cases.monitor_driver import MonitorDriverUseCase
from driver_fatigue.config.settings import AppSettings
from driver_fatigue.domain.value_objects import (
    CalibrationSettings,
    FatigueThresholds,
    FrameQualityPolicy,
)
from driver_fatigue.infrastructure.alert_sinks.composite import CompositeSink
from driver_fatigue.infrastructure.alert_sinks.http_webhook import HttpWebhookSink
from driver_fatigue.infrastructure.alert_sinks.jsonl import JsonlEventSink
from driver_fatigue.infrastructure.alert_sinks.log import LogSink
from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink
from driver_fatigue.infrastructure.alert_sinks.sound import SoundSink
from driver_fatigue.infrastructure.context_validators.noop import NoopContextValidator
from driver_fatigue.infrastructure.detectors.mediapipe_detector import MediapipeFaceDetector
from driver_fatigue.infrastructure.presenters.composite import CompositePresenter
from driver_fatigue.infrastructure.presenters.file_recorder import FileRecorderPresenter
from driver_fatigue.infrastructure.presenters.headless import HeadlessPresenter
from driver_fatigue.infrastructure.presenters.mjpeg_push import MjpegStreamPresenter
from driver_fatigue.infrastructure.presenters.opencv_window import OpenCvWindowPresenter
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer
from driver_fatigue.infrastructure.rendering.theme import RenderingTheme
from driver_fatigue.infrastructure.video_sources.file import FileVideoSource
from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource
from driver_fatigue.infrastructure.video_sources.webcam import WebcamVideoSource

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
            return SoundSink(
                sound_path=settings.alarm_sound_path,
                start_volume=settings.sound_sink.start_volume,
                peak_volume=settings.sound_sink.peak_volume,
                ramp_seconds=settings.sound_sink.ramp_seconds,
                cooldown_seconds=settings.sound_sink.cooldown_seconds,
            )
        except Exception:
            _log.warning("SoundSink indisponivel, ignorando")
            return None
    if name == "http":
        cfg = settings.http_webhook
        assert cfg is not None
        return HttpWebhookSink(
            url=cfg.url, bearer_token=cfg.bearer_token,
            timeout_seconds=cfg.timeout_seconds,
            api_key=settings.web.api_key,
        )
    if name == "mqtt":
        cfg = settings.mqtt
        assert cfg is not None
        return MqttSink(
            broker=cfg.broker, port=cfg.port, topic=cfg.topic,
            username=cfg.username, password=cfg.password,
        )
    if name == "jsonl":
        return JsonlEventSink(path=settings.jsonl.path)
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
    extras: list = []
    if settings.recording.path is not None:
        extras.append(FileRecorderPresenter(
            renderer=renderer,
            output_path=settings.recording.path,
            fps=settings.recording.fps,
            codec=settings.recording.codec,
        ))
    if settings.dashboard_stream.enabled:
        extras.append(MjpegStreamPresenter(
            renderer=renderer,
            push_url=settings.dashboard_stream.push_url,
            jpeg_quality=settings.dashboard_stream.jpeg_quality,
            max_fps=settings.dashboard_stream.max_fps,
            api_key=settings.web.api_key,
        ))
    if not extras:
        return main
    return CompositePresenter(main, *extras)


def _build_calibration(settings: AppSettings) -> CalibrationSettings:
    cfg = settings.calibration
    return CalibrationSettings(
        enabled=cfg.enabled,
        warmup_frames=cfg.warmup_frames,
        ear_close_ratio=cfg.ear_close_ratio,
        mar_open_zscore=cfg.mar_open_zscore,
    )


def _build_quality_policy(settings: AppSettings) -> FrameQualityPolicy:
    cfg = settings.frame_quality
    if not cfg.enabled:
        return FrameQualityPolicy()
    return FrameQualityPolicy(
        min_face_confidence=cfg.min_face_confidence,
        min_face_area_ratio=cfg.min_face_area_ratio,
        max_head_yaw_deg=cfg.max_head_yaw_deg,
        max_head_pitch_deg=cfg.max_head_pitch_deg,
    )


def _build_validator(settings: AppSettings) -> ContextValidatorPort | None:
    cfg = settings.context_validator
    if cfg.kind == "noop":
        return None
    if cfg.kind == "eye_state":
        try:
            from driver_fatigue.infrastructure.context_validators.eye_state_onnx import (
                EyeStateContextValidator,
            )
        except Exception as exc:
            _log.warning(
                "EyeStateContextValidator indisponivel (%s); usando noop", exc,
            )
            return None
        try:
            return EyeStateContextValidator(
                model_path=cfg.eye_state_model_path,
                perclos_window_seconds=cfg.perclos_window_seconds,
                perclos_threshold=cfg.perclos_threshold,
            )
        except Exception as exc:
            _log.warning(
                "Falha ao construir EyeStateContextValidator (%s); usando noop", exc,
            )
            return None
    return NoopContextValidator()


def _build_index_evaluator(settings: AppSettings):
    """Constroi o motor de fusao multimodal.

    Retorna NoOp se desabilitado ou se scikit-fuzzy nao estiver instalado.
    """
    from driver_fatigue.infrastructure.index_evaluators.noop import NoOpIndexEvaluator

    if not settings.fatigue_index.enabled:
        return NoOpIndexEvaluator()
    try:
        from driver_fatigue.infrastructure.index_evaluators.fuzzy import (
            FuzzyIndexEvaluator,
        )
        return FuzzyIndexEvaluator()
    except ImportError:
        _log.warning(
            "scikit-fuzzy nao instalado; rodando sem indice de fadiga. "
            "Instale com: pip install -e \".[fuzzy]\""
        )
        return NoOpIndexEvaluator()


def build_monitor_use_case(
    settings: AppSettings,
    source_override: VideoSourcePort | None = None,
    sound_override: Literal["disabled"] | None = None,
    validator_override: ContextValidatorPort | None = None,
    sink_override: AlertSinkPort | None = None,
    presenter_override: FramePresenterPort | None = None,
) -> MonitorDriverUseCase:
    source = source_override if source_override is not None else _build_source(settings)
    detector = MediapipeFaceDetector()
    thresholds = FatigueThresholds(
        ear_threshold=settings.thresholds.ear_threshold,
        mar_threshold=settings.thresholds.mar_threshold,
        consecutive_frames=settings.thresholds.consecutive_frames,
        warning_ratio=settings.thresholds.warning_ratio,
        recovery_frames=settings.thresholds.recovery_frames,
        min_alert_duration_frames=settings.thresholds.min_alert_duration_frames,
        alarm_cooldown_seconds=settings.thresholds.alarm_cooldown_seconds,
        yawn_window_frames=settings.thresholds.yawn_window_frames,
        yawn_stability_max=settings.thresholds.yawn_stability_max,
        head_drop_pitch_deg=settings.thresholds.head_drop_pitch_deg,
        head_drop_frames_threshold=settings.thresholds.head_drop_frames_threshold,
    )
    calibration = _build_calibration(settings)
    quality_policy = _build_quality_policy(settings)
    detect = DetectFatigueUseCase(
        detector=detector,
        thresholds=thresholds,
        calibration=calibration,
        quality_policy=quality_policy,
    )
    sink = sink_override if sink_override is not None else _build_sinks(settings, sound_override=sound_override)
    if presenter_override is not None:
        presenter = presenter_override
    else:
        renderer = _build_renderer(settings)
        presenter = _build_presenter(settings, renderer)
    validator = validator_override if validator_override is not None else _build_validator(settings)
    state_publisher = _resolve_state_publisher(sink)
    return MonitorDriverUseCase(
        source=source, detect=detect, sink=sink, presenter=presenter,
        context_validator=validator,
        min_validator_confidence=settings.context_validator.min_confidence,
        fail_safe_on_error=settings.context_validator.fail_safe_on_error,
        state_publisher=state_publisher,
        state_publish_every_frames=settings.dashboard_stream.state_publish_every_frames,
    )


def _resolve_state_publisher(sink):
    """Desempacota CompositeSink procurando alguém com publish_state."""
    candidates = []
    if hasattr(sink, "_sinks"):  # CompositeSink
        candidates.extend(sink._sinks)
    else:
        candidates.append(sink)
    for s in candidates:
        if hasattr(s, "publish_state"):
            return s.publish_state
    return None
