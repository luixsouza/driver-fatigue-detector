"""Regra central de decisão sobre fadiga, a partir de landmarks.

Pipeline:
  1. Calcular EAR/MAR do frame.
  2. Atualizar PersonalBaseline durante warmup (e continuamente em frames "normais").
  3. Aplicar thresholds *relativos* ao baseline quando calibrado.
  4. Discriminar fala vs bocejo via janela deslizante de MAR.
  5. Aplicar histerese (entrada usa consecutive_frames * warning_ratio, saída usa recovery_frames).
  6. Aplicar cooldown global de alarme.

Nota sobre `warning_ratio`: por compatibilidade com Fase 1, é o *cutoff de
entrada em ALERT* (alert_cutoff = int(consecutive_frames * warning_ratio)).
Frames com 0 < consecutive < alert_cutoff são "warning". O nome do campo é
herdado e mantemos para não quebrar configs existentes.
"""
from __future__ import annotations

from statistics import pstdev

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState
from driver_fatigue.domain.metrics import eye_aspect_ratio, mouth_aspect_ratio
from driver_fatigue.domain.value_objects import (
    CalibrationSettings,
    FatigueThresholds,
    FrameQuality,
    PersonalBaseline,
)


def _effective_thresholds(
    thresholds: FatigueThresholds,
    calibration: CalibrationSettings,
    baseline: PersonalBaseline,
) -> tuple[float, float]:
    if not calibration.enabled or not baseline.is_calibrated(calibration.warmup_frames):
        return thresholds.ear_threshold, thresholds.mar_threshold
    ear_eff = baseline.ear_rest * calibration.ear_close_ratio
    mar_eff = baseline.mar_rest + calibration.mar_open_zscore * max(baseline.mar_std, 1e-3)
    return ear_eff, mar_eff


def _is_sustained_yawn(
    mar_window: tuple[float, ...],
    current_mar: float,
    mar_threshold: float,
    yawn_window_frames: int,
    yawn_stability_max: float,
) -> bool:
    full = (*mar_window, current_mar)
    if len(full) < yawn_window_frames:
        return current_mar > mar_threshold
    window = full[-yawn_window_frames:]
    if min(window) <= mar_threshold:
        return False
    return pstdev(window) <= yawn_stability_max


def _push_window(
    window: tuple[float, ...],
    value: float,
    capacity: int,
) -> tuple[float, ...]:
    new = (*window, value)
    if len(new) <= capacity:
        return new
    return new[-capacity:]


def evaluate_fatigue(
    landmarks: FaceLandmarks,
    thresholds: FatigueThresholds,
    previous: FatigueState,
    *,
    calibration: CalibrationSettings = CalibrationSettings(enabled=False),
    quality: FrameQuality | None = None,
    timestamp: float | None = None,
) -> FatigueState:
    q = quality if quality is not None else FrameQuality.trusted()
    if not q.trustworthy:
        return _replace(previous, quality=q)

    left_ear = eye_aspect_ratio(landmarks.left_eye_contour)
    right_ear = eye_aspect_ratio(landmarks.right_eye_contour)
    ear = (left_ear + right_ear) / 2.0
    mar = mouth_aspect_ratio(landmarks.mouth_outer)

    baseline = previous.baseline
    if calibration.enabled and not baseline.is_calibrated(calibration.warmup_frames):
        baseline = baseline.absorb(ear, mar)
        return FatigueState(
            ear=ear, mar=mar,
            consecutive_frames=0,
            is_fatigued=False, is_yawning=False,
            severity="normal",
            recovery_frames=0,
            last_alert_timestamp=previous.last_alert_timestamp,
            baseline=baseline,
            quality=q,
            mar_window=_push_window(previous.mar_window, mar, thresholds.yawn_window_frames),
        )

    ear_threshold, mar_threshold = _effective_thresholds(thresholds, calibration, baseline)

    eyes_closed = ear < ear_threshold
    yawning = _is_sustained_yawn(
        previous.mar_window, mar, mar_threshold,
        thresholds.yawn_window_frames, thresholds.yawn_stability_max,
    )
    triggered = eyes_closed or yawning

    alert_cutoff = max(int(thresholds.consecutive_frames * thresholds.warning_ratio), 1)
    last_alert_ts = previous.last_alert_timestamp
    now = timestamp if timestamp is not None else previous.last_alert_timestamp

    if triggered:
        consecutive = previous.consecutive_frames + 1
        recovery = 0
    else:
        consecutive = previous.consecutive_frames
        recovery = previous.recovery_frames + 1
        # Reset do contador depende do estado anterior:
        if previous.severity == "alert":
            held_long_enough = (
                thresholds.min_alert_duration_frames == 0
                or previous.consecutive_frames
                   >= alert_cutoff + thresholds.min_alert_duration_frames
            )
            if recovery >= max(thresholds.recovery_frames, 1) and held_long_enough:
                consecutive = 0
        else:
            # warning/normal: qualquer frame limpo zera (Fase 1)
            consecutive = 0

    if previous.severity == "alert" and consecutive > 0:
        severity = "alert"
    elif consecutive >= alert_cutoff:
        if (
            thresholds.alarm_cooldown_seconds > 0
            and last_alert_ts >= 0.0
            and now >= 0.0
            and (now - last_alert_ts) < thresholds.alarm_cooldown_seconds
        ):
            severity = "warning"
        else:
            severity = "alert"
            if now >= 0.0:
                last_alert_ts = now
    elif consecutive > 0:
        severity = "warning"
    else:
        severity = "normal"

    if (
        calibration.enabled
        and severity == "normal"
        and not triggered
        and baseline.is_calibrated(calibration.warmup_frames)
    ):
        baseline = baseline.absorb(ear, mar)

    return FatigueState(
        ear=ear,
        mar=mar,
        consecutive_frames=consecutive,
        is_fatigued=(severity == "alert"),
        is_yawning=(yawning and severity != "normal"),
        severity=severity,
        recovery_frames=recovery,
        last_alert_timestamp=last_alert_ts,
        baseline=baseline,
        quality=q,
        mar_window=_push_window(previous.mar_window, mar, thresholds.yawn_window_frames),
    )


def _replace(state: FatigueState, **changes) -> FatigueState:
    return FatigueState(
        ear=changes.get("ear", state.ear),
        mar=changes.get("mar", state.mar),
        consecutive_frames=changes.get("consecutive_frames", state.consecutive_frames),
        is_fatigued=changes.get("is_fatigued", state.is_fatigued),
        is_yawning=changes.get("is_yawning", state.is_yawning),
        severity=changes.get("severity", state.severity),
        recovery_frames=changes.get("recovery_frames", state.recovery_frames),
        last_alert_timestamp=changes.get("last_alert_timestamp", state.last_alert_timestamp),
        baseline=changes.get("baseline", state.baseline),
        quality=changes.get("quality", state.quality),
        mar_window=changes.get("mar_window", state.mar_window),
    )
