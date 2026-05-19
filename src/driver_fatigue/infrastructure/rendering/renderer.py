from __future__ import annotations

import time

import cv2
import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.infrastructure.rendering.theme import RenderingTheme
from driver_fatigue.infrastructure.rendering.curves import catmull_rom_closed
from driver_fatigue.infrastructure.rendering.glow import apply_glow
from driver_fatigue.infrastructure.rendering.hud import draw_hud
from driver_fatigue.infrastructure.rendering.overlay import draw_filled_overlay


class FrameRenderer:
    """Produz o frame com overlay completo. Sem efeitos colaterais externos."""

    def __init__(self, theme: RenderingTheme) -> None:
        self._theme = theme
        self._last_ts: float | None = None
        self._fps_ema: float = 0.0

    def _color_for(self, severity: str) -> tuple[int, int, int]:
        if severity == "alert":
            return self._theme.color_alert
        if severity == "warning":
            return self._theme.color_warning
        return self._theme.color_normal

    def _smooth(self, pts) -> np.ndarray:
        return catmull_rom_closed(pts, self._theme.smoothing_steps)

    def _update_fps(self, ts: float) -> float:
        if self._last_ts is not None:
            dt = max(1e-6, ts - self._last_ts)
            inst = 1.0 / dt
            self._fps_ema = 0.9 * self._fps_ema + 0.1 * inst if self._fps_ema else inst
        self._last_ts = ts
        return self._fps_ema

    def render(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> np.ndarray:
        img = frame.image.copy()
        color = self._color_for(state.severity)

        for lm in landmarks_list:
            if self._theme.show_face_oval:
                face_curve = self._smooth(lm.face_oval)
                cv2.polylines(
                    img, [face_curve.astype(np.int32)],
                    isClosed=True, color=color, thickness=1, lineType=cv2.LINE_AA,
                )

            for region in (lm.left_eye_contour, lm.right_eye_contour):
                curve = self._smooth(region)
                img = draw_filled_overlay(img, curve, color, self._theme.overlay_alpha)
                cv2.polylines(
                    img, [curve.astype(np.int32)],
                    isClosed=True, color=color, thickness=2, lineType=cv2.LINE_AA,
                )

            for region in (lm.mouth_outer,):
                curve = self._smooth(region)
                img = draw_filled_overlay(img, curve, color, self._theme.overlay_alpha)
                cv2.polylines(
                    img, [curve.astype(np.int32)],
                    isClosed=True, color=color, thickness=2, lineType=cv2.LINE_AA,
                )

            for iris in (lm.left_iris, lm.right_iris):
                if iris is None:
                    continue
                cx = int(sum(p.x for p in iris) / len(iris))
                cy = int(sum(p.y for p in iris) / len(iris))
                cv2.circle(img, (cx, cy), 4, color, 1, cv2.LINE_AA)
                cv2.circle(img, (cx, cy), 2, color, -1, cv2.LINE_AA)

        if self._theme.glow_enabled:
            img = apply_glow(img, self._theme.glow_sigma)

        if state.severity == "alert":
            h, w = img.shape[:2]
            vignette = np.zeros_like(img)
            cv2.rectangle(vignette, (0, 0), (w, h), self._theme.color_alert, -1)
            img = cv2.addWeighted(vignette, 0.15, img, 1.0, 0)
            cv2.putText(
                img, "FADIGA DETECTADA",
                (20, 40), cv2.FONT_HERSHEY_DUPLEX, 1.0,
                self._theme.color_alert, 2, cv2.LINE_AA,
            )

        if self._theme.show_hud:
            fps = self._update_fps(frame.timestamp or time.monotonic())
            baseline_label = None
            if state.baseline.sample_count > 0:
                if state.baseline.sample_count < 30:
                    baseline_label = f"calibrating {state.baseline.sample_count}"
                else:
                    baseline_label = (
                        f"baseline EAR {state.baseline.ear_rest:.2f} "
                        f"MAR {state.baseline.mar_rest:.2f}"
                    )
            quality_label = None
            if state.quality.trustworthy:
                if baseline_label:
                    quality_label = "QUALITY OK"
            else:
                quality_label = f"QUALITY skip ({state.quality.reason})"
            img = draw_hud(
                img,
                ear=state.ear, mar=state.mar,
                consecutive=state.consecutive_frames,
                fps=fps, severity=state.severity,
                max_consecutive=max(1, state.consecutive_frames + 1),
                quality_label=quality_label,
                baseline_label=baseline_label,
            )

        return img
