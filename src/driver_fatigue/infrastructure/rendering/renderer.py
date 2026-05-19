from __future__ import annotations

import time

import cv2
import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.infrastructure.rendering.glow import apply_glow
from driver_fatigue.infrastructure.rendering.hud import draw_hud
from driver_fatigue.infrastructure.rendering.mesh_connections import (
    CONTOURS,
    LEFT_EYE,
    LEFT_IRIS,
    LIPS,
    RIGHT_EYE,
    RIGHT_IRIS,
    TESSELATION,
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
        """Desenha mesh completo: tesselacao (~2700 linhas finas) +
        contornos faciais brilhantes + olhos/boca destacados + 468 pontos."""
        if not all_points or len(all_points) < 468:
            return
        n = len(all_points)
        # Pré-converte pra inteiros uma vez só (cv2 quer tuplas int).
        pts_int = [(int(p.x), int(p.y)) for p in all_points]

        # 1. TESSELATION completa — linhas finas com cor bem atenuada.
        # Sem antialiasing porque sao milhares de linhas, AA dobra o custo.
        mesh_color = tuple(int(c * 0.35) for c in color)
        for a, b in TESSELATION:
            if a < n and b < n:
                cv2.line(img, pts_int[a], pts_int[b], mesh_color, 1)

        # 2. CONTOURS faciais (oval, sobrancelhas, nariz, etc) — cor cheia,
        # ainda fina mas com AA pra leitura limpa.
        for a, b in CONTOURS:
            if a < n and b < n:
                cv2.line(img, pts_int[a], pts_int[b], color, 1, cv2.LINE_AA)

        # 3. Olhos + boca em destaque — linha grossa.
        for connections in (LEFT_EYE, RIGHT_EYE, LIPS):
            for a, b in connections:
                if a < n and b < n:
                    cv2.line(img, pts_int[a], pts_int[b], color, 2, cv2.LINE_AA)

        # 4. Iris (se disponivel) — circulos pequenos.
        for connections in (LEFT_IRIS, RIGHT_IRIS):
            for a, b in connections:
                if a < n and b < n:
                    cv2.line(img, pts_int[a], pts_int[b], color, 1, cv2.LINE_AA)

        # 5. Todos os 468 landmarks como pontos discretos (1px). Da leitura
        # visual dos vertices mesmo em frames muito rapidos.
        dot_color = tuple(int(c * 0.85) for c in color)
        for p in pts_int:
            cv2.circle(img, p, 1, dot_color, -1)

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
