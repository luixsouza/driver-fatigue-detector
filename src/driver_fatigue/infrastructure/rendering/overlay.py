from __future__ import annotations

import cv2
import numpy as np


def draw_filled_overlay(
    image: np.ndarray,
    polygon: np.ndarray,
    color: tuple[int, int, int],
    alpha: float,
) -> np.ndarray:
    """Desenha polígono preenchido sobre uma cópia de `image` com transparência alpha."""
    layer = image.copy()
    cv2.fillPoly(layer, [polygon.astype(np.int32)], color, lineType=cv2.LINE_AA)
    return cv2.addWeighted(layer, alpha, image, 1.0 - alpha, 0)
