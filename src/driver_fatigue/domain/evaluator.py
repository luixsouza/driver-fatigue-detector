"""Regra central de decisão sobre fadiga, a partir de landmarks."""
from __future__ import annotations

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState
from driver_fatigue.domain.metrics import eye_aspect_ratio, mouth_aspect_ratio
from driver_fatigue.domain.value_objects import FatigueThresholds


def evaluate_fatigue(
    landmarks: FaceLandmarks,
    thresholds: FatigueThresholds,
    previous: FatigueState,
) -> FatigueState:
    left_ear = eye_aspect_ratio(landmarks.left_eye_contour)
    right_ear = eye_aspect_ratio(landmarks.right_eye_contour)
    ear = (left_ear + right_ear) / 2.0
    mar = mouth_aspect_ratio(landmarks.mouth_outer)

    eyes_closed = ear < thresholds.ear_threshold
    yawning = mar > thresholds.mar_threshold
    triggered = eyes_closed or yawning

    if triggered:
        consecutive = previous.consecutive_frames + 1
    else:
        consecutive = 0

    warning_cutoff = int(thresholds.consecutive_frames * thresholds.warning_ratio)
    if consecutive >= warning_cutoff and consecutive > 0:
        severity = "alert"
    elif consecutive > 0:
        severity = "warning"
    else:
        severity = "normal"

    return FatigueState(
        ear=ear,
        mar=mar,
        consecutive_frames=consecutive,
        is_fatigued=(severity == "alert"),
        is_yawning=(yawning and consecutive > 0),
        severity=severity,
    )
