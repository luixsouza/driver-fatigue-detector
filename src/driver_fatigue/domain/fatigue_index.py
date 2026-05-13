"""Motor de fusao multimodal — logica de dominio.

Por enquanto so contem a curva circadiana usada como entrada do motor
de fusao. Value objects e Protocol do evaluator entram em commits
subsequentes.
"""
from __future__ import annotations


def circadian_risk(hour_of_day: float) -> float:
    """Risco circadiano em [0, 1] em funcao da hora do dia.

    - 02:00-06:00: 0.9 (vale circadiano noturno)
    - 14:00-16:00: 0.6 (vale pos-prandial)
    - resto:       0.1
    - transicoes lineares de 1h nas bordas

    Args:
        hour_of_day: 0.0-23.99 (clampado se fora)
    """
    h = max(0.0, min(23.99, hour_of_day))

    def _bump(center_start: float, center_end: float, peak: float) -> float:
        # 1h de rampa subindo antes de center_start, 1h descendo apos center_end
        ramp = 1.0
        base = 0.1
        if center_start - ramp <= h <= center_end + ramp:
            if h <= center_start:
                # rampa subindo antes de e em center_start
                t = (h - (center_start - ramp)) / ramp
                return base + (peak - base) * t
            elif h <= center_end:
                # plateau no pico
                return peak
            else:
                # rampa descendo apos center_end
                t = 1.0 - (h - center_end) / ramp
                return base + (peak - base) * t
        return base

    night = _bump(2.0, 6.0, 0.9)
    afternoon = _bump(14.0, 16.0, 0.6)
    return max(night, afternoon)
