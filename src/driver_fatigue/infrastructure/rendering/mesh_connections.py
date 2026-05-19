"""Reexporta as topologias FaceMesh oficiais embarcadas em _facemesh_data.

A versão 0.10+ do mediapipe (somente Tasks API) não inclui mais o módulo
`mp.solutions.face_mesh`. As constantes (FACEMESH_TESSELATION, CONTOURS,
LIPS, etc.) foram embarcadas do repositório oficial em _facemesh_data.py
(Apache 2.0, sem modificações).
"""
from __future__ import annotations

from driver_fatigue.infrastructure.rendering._facemesh_data import (
    FACEMESH_CONTOURS,
    FACEMESH_FACE_OVAL,
    FACEMESH_LEFT_EYE,
    FACEMESH_LEFT_EYEBROW,
    FACEMESH_LEFT_IRIS,
    FACEMESH_LIPS,
    FACEMESH_RIGHT_EYE,
    FACEMESH_RIGHT_EYEBROW,
    FACEMESH_RIGHT_IRIS,
    FACEMESH_TESSELATION,
)

# Aliases curtos pra renderer
TESSELATION = list(FACEMESH_TESSELATION)
CONTOURS = list(FACEMESH_CONTOURS)
LIPS = list(FACEMESH_LIPS)
LEFT_EYE = list(FACEMESH_LEFT_EYE)
RIGHT_EYE = list(FACEMESH_RIGHT_EYE)
LEFT_EYEBROW = list(FACEMESH_LEFT_EYEBROW)
RIGHT_EYEBROW = list(FACEMESH_RIGHT_EYEBROW)
FACE_OVAL = list(FACEMESH_FACE_OVAL)
LEFT_IRIS = list(FACEMESH_LEFT_IRIS)
RIGHT_IRIS = list(FACEMESH_RIGHT_IRIS)
