from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderingTheme:
    color_normal: tuple[int, int, int] = (255, 255, 0)
    color_warning: tuple[int, int, int] = (0, 200, 255)
    color_alert: tuple[int, int, int] = (50, 50, 255)
    overlay_alpha: float = 0.35
    glow_enabled: bool = True
    glow_sigma: int = 15
    show_hud: bool = True
    show_face_oval: bool = True
    smoothing_steps: int = 20

    def __post_init__(self) -> None:
        if not 0.0 <= self.overlay_alpha <= 1.0:
            raise ValueError("overlay_alpha deve estar em [0, 1]")
        if self.smoothing_steps < 0:
            raise ValueError("smoothing_steps não pode ser negativo")
        if self.glow_sigma < 0:
            raise ValueError("glow_sigma não pode ser negativo")
