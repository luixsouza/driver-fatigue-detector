from __future__ import annotations

import cv2
import numpy as np

_COLOR_BY_SEVERITY = {
    "normal": (200, 200, 200),
    "warning": (0, 200, 255),
    "alert": (50, 50, 255),
}


def draw_hud(
    image: np.ndarray,
    ear: float,
    mar: float,
    consecutive: int,
    fps: float,
    severity: str,
    max_consecutive: int,
    quality_label: str | None = None,
    baseline_label: str | None = None,
) -> np.ndarray:
    """Desenha painel inferior translúcido com métricas.

    `quality_label` e `baseline_label` são opcionais — quando dados,
    aparecem numa segunda linha (status de calibração + gate de qualidade).
    """
    out = image.copy()
    h, w = out.shape[:2]
    show_status_line = bool(quality_label or baseline_label)
    panel_h = 80 if show_status_line else 60
    panel = np.zeros_like(out)
    cv2.rectangle(panel, (0, h - panel_h), (w, h), (40, 40, 40), -1)
    blended = cv2.addWeighted(panel, 0.6, out, 1.0, 0)

    color = _COLOR_BY_SEVERITY.get(severity, (200, 200, 200))
    font = cv2.FONT_HERSHEY_DUPLEX
    metrics_y = h - (55 if show_status_line else 35)
    cv2.putText(blended, f"EAR {ear:.2f}", (10, metrics_y), font, 0.55, color, 1, cv2.LINE_AA)
    cv2.putText(blended, f"MAR {mar:.2f}", (110, metrics_y), font, 0.55, color, 1, cv2.LINE_AA)
    cv2.putText(blended, f"FPS {fps:.1f}", (210, metrics_y), font, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(blended, severity.upper(), (w - 120, metrics_y), font, 0.6, color, 1, cv2.LINE_AA)

    if show_status_line:
        status = " | ".join(s for s in (baseline_label, quality_label) if s)
        cv2.putText(
            blended, status, (10, h - 30), font, 0.45,
            (180, 180, 180), 1, cv2.LINE_AA,
        )

    bar_x0, bar_x1 = 10, w - 10
    bar_y = h - 12
    cv2.rectangle(blended, (bar_x0, bar_y), (bar_x1, bar_y + 4), (80, 80, 80), -1)
    ratio = min(1.0, consecutive / max(1, max_consecutive))
    fill_x = int(bar_x0 + (bar_x1 - bar_x0) * ratio)
    cv2.rectangle(blended, (bar_x0, bar_y), (fill_x, bar_y + 4), color, -1)
    return blended
