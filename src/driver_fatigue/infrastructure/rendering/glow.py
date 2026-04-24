from __future__ import annotations

import cv2
import numpy as np


def apply_glow(image: np.ndarray, sigma: int) -> np.ndarray:
    """Retorna `image` com efeito glow aditivo sobre pixels brilhantes."""
    if sigma <= 0:
        return image
    k = sigma * 2 + 1
    blurred = cv2.GaussianBlur(image, (k, k), sigma)
    return cv2.add(image, blurred)
