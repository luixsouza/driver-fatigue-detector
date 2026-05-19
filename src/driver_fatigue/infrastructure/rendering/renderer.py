from __future__ import annotations

import time

import cv2
import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.infrastructure.rendering.glow import apply_glow
from driver_fatigue.infrastructure.rendering.hud import draw_hud
from driver_fatigue.infrastructure.rendering.mesh_connections import (
    HIGHLIGHT_CONNECTIONS,
    STRUCTURAL_CONNECTIONS,
)
from driver_fatigue.infrastructure.rendering.theme import RenderingTheme


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

    def _update_fps(self, ts: float) -> float:
        if self._last_ts is not None:
            dt = max(1e-6, ts - self._last_ts)
            inst = 1.0 / dt
            self._fps_ema = 0.9 * self._fps_ema + 0.1 * inst if self._fps_ema else inst
        self._last_ts = ts
        return self._fps_ema

    def _draw_mesh(
        self,
        img: np.ndarray,
        all_points: tuple,
        color: tuple[int, int, int],
    ) -> None:
        """Desenha conexões estruturais (finas) + destacadas (grossas) usando
        os 468 landmarks. Único loop, single-pass — barato visualmente."""
        if not all_points or len(all_points) < 468:
            return
        # Pré-converte landmarks pra inteiros uma vez só (evita repetir em
        # cada linha). Linha cv2.line é mais rápida que polylines pequenos.
        pts_int = [(int(p.x), int(p.y)) for p in all_points]

        # Estrutural: linhas finas, cor levemente atenuada
        attenuated = tuple(int(c * 0.55) for c in color)
        for a, b in STRUCTURAL_CONNECTIONS:
            if a < len(pts_int) and b < len(pts_int):
                cv2.line(img, pts_int[a], pts_int[b], attenuated, 1, cv2.LINE_AA)

        # Destacadas (olhos+boca): linhas grossas com cor cheia
        for a, b in HIGHLIGHT_CONNECTIONS:
            if a < len(pts_int) and b < len(pts_int):
                cv2.line(img, pts_int[a], pts_int[b], color, 2, cv2.LINE_AA)

        # Pontos discretos nos vértices destacados (eye/mouth) — dá leitura
        # de qualquer ângulo, robusto a rosto de lado.
        seen_pts: set[int] = set()
        for a, b in HIGHLIGHT_CONNECTIONS:
            for idx in (a, b):
                if idx in seen_pts or idx >= len(pts_int):
                    continue
                seen_pts.add(idx)
                cv2.circle(img, pts_int[idx], 2, color, -1, cv2.LINE_AA)

    def render(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> np.ndarray:
        img = frame.image.copy()
        color = self._color_for(state.severity)

        for lm in landmarks_list:
            # Mesh completo a partir dos 468 landmarks (fallback gracioso
            # se não vier all_points — preserva compatibilidade com mocks).
            if lm.all_points:
                self._draw_mesh(img, lm.all_points, color)
            elif self._theme.show_face_oval:
                # Fallback legacy: só o oval do rosto
                pts = np.array([(int(p.x), int(p.y)) for p in lm.face_oval])
                cv2.polylines(img, [pts], True, color, 1, cv2.LINE_AA)

            # Iris destaca-se com circulo cheio (não vem nos mesh connections)
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
