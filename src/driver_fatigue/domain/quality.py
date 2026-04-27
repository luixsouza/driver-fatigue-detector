"""Estima a confiabilidade do frame a partir dos landmarks faciais.

Usa proxies geométricos baratos (sem solvePnP):
  - yaw via assimetria horizontal: razão das larguras dos dois olhos.
    Cabeça virada faz um olho aparecer significativamente menor que o outro.
  - pitch via razão vertical: distância (centro_olhos → centro_face_oval)
    contra a metade da altura do oval. Cabeça caindo desloca os olhos pra cima
    do centro do oval.
  - face_area_ratio: bbox do face_oval / área do frame.
  - detector_confidence: passado externamente (MediaPipe já filtra por
    min_face_detection_confidence, então landmarks que chegam aqui já
    passaram um threshold mínimo — usamos 1.0 como aproximação segura).
"""
from __future__ import annotations

import math
from typing import Sequence

from driver_fatigue.domain.entities import FaceLandmarks, Point
from driver_fatigue.domain.value_objects import FrameQuality, FrameQualityPolicy


def _bounds(points: Sequence[Point]) -> tuple[float, float, float, float]:
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _eye_width(eye: Sequence[Point]) -> float:
    if len(eye) < 4:
        return 0.0
    return math.hypot(eye[0].x - eye[3].x, eye[0].y - eye[3].y)


def estimate_yaw_deg(landmarks: FaceLandmarks) -> float:
    """Yaw aproximado via razão das larguras aparentes dos dois olhos.

    Quando o rosto está de frente, ambas as larguras são iguais → yaw=0.
    Quando vira pra um lado, o olho do lado oposto encolhe na imagem.
    Mapeamento empírico: assimetria de 0.5 ≈ ±60° (saturação).
    """
    lw = _eye_width(landmarks.left_eye_contour)
    rw = _eye_width(landmarks.right_eye_contour)
    total = lw + rw
    if total <= 0:
        return 0.0
    asymmetry = (lw - rw) / total  # range ~ [-1, 1]
    return max(-90.0, min(90.0, asymmetry * 120.0))


def estimate_pitch_deg(landmarks: FaceLandmarks) -> float:
    """Pitch aproximado via posição vertical dos olhos no oval.

    Centro dos olhos comparado ao centro vertical do face_oval. Cabeça
    caindo (pitch positivo no sentido "queixo no peito") empurra olhos
    pra cima do centro do oval.
    """
    if not landmarks.face_oval:
        return 0.0
    eyes = (*landmarks.left_eye_contour, *landmarks.right_eye_contour)
    if not eyes:
        return 0.0
    eye_center_y = sum(p.y for p in eyes) / len(eyes)
    y_min, y_max = min(p.y for p in landmarks.face_oval), max(p.y for p in landmarks.face_oval)
    half = (y_max - y_min) / 2.0
    if half <= 0:
        return 0.0
    oval_center_y = (y_min + y_max) / 2.0
    offset = (eye_center_y - oval_center_y) / half  # ~ [-1, 1]
    return max(-90.0, min(90.0, offset * 90.0))


def estimate_face_area_ratio(
    landmarks: FaceLandmarks,
    frame_width: int,
    frame_height: int,
) -> float:
    if frame_width <= 0 or frame_height <= 0 or not landmarks.face_oval:
        return 0.0
    x0, y0, x1, y1 = _bounds(landmarks.face_oval)
    bbox_area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    frame_area = float(frame_width * frame_height)
    return bbox_area / frame_area


def estimate_quality(
    landmarks: FaceLandmarks,
    frame_width: int,
    frame_height: int,
    policy: FrameQualityPolicy,
    detector_confidence: float = 1.0,
) -> FrameQuality:
    return policy.evaluate(
        head_yaw_deg=estimate_yaw_deg(landmarks),
        head_pitch_deg=estimate_pitch_deg(landmarks),
        face_area_ratio=estimate_face_area_ratio(landmarks, frame_width, frame_height),
        detector_confidence=detector_confidence,
    )
