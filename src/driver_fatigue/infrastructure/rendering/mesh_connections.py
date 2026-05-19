"""Conexões topológicas da face mesh MediaPipe (468 landmarks).

Subconjunto curado pra mesh visualmente limpo — não usa as ~2700 conexões
de FACEMESH_TESSELATION completa (visualmente ruidoso); foca em estruturas
anatômicas relevantes pra detecção de fadiga: olhos, sobrancelhas, boca,
nariz, contorno facial.
"""
from __future__ import annotations

# Contorno do rosto (já temos FACE_OVAL_INDICES no detector, replicamos aqui)
FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]

# Olhos — contorno completo (16 pts) pra desenho fino
LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]

# Sobrancelhas
LEFT_EYEBROW = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
RIGHT_EYEBROW = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]

# Boca — outer + inner
LIPS_OUTER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]
LIPS_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95]

# Nariz — ponte + base
NOSE_BRIDGE = [168, 6, 197, 195, 5, 4, 1, 19]
NOSE_BASE = [98, 97, 2, 326, 327]

# Iris (apenas se MediaPipe retornar — depende da versão do modelo)
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]


def closed_polyline_indices(indices: list[int]) -> list[tuple[int, int]]:
    """Gera lista de pares (a, b) formando polilinha fechada."""
    out = []
    n = len(indices)
    for i in range(n):
        out.append((indices[i], indices[(i + 1) % n]))
    return out


# Conexões "estruturais" — desenhadas finas pra dar volume sem poluir
STRUCTURAL_CONNECTIONS: list[tuple[int, int]] = (
    closed_polyline_indices(FACE_OVAL)
    + closed_polyline_indices(LEFT_EYEBROW)
    + closed_polyline_indices(RIGHT_EYEBROW)
    + closed_polyline_indices(NOSE_BRIDGE)
    + closed_polyline_indices(NOSE_BASE)
)

# Conexões "destacadas" — olhos e boca, desenhadas mais grossas
HIGHLIGHT_CONNECTIONS: list[tuple[int, int]] = (
    closed_polyline_indices(LEFT_EYE)
    + closed_polyline_indices(RIGHT_EYE)
    + closed_polyline_indices(LIPS_OUTER)
    + closed_polyline_indices(LIPS_INNER)
)
