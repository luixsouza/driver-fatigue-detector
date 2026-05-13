"""Testes de comportamento do motor fuzzy.

Cobrimos cada caso de fadiga prototipico do spec. Os limites de severity
sao: < 35 normal, 35-60 warning, 60-80 alert, >= 80 alert+critical.
"""
import pytest

skfuzzy = pytest.importorskip("skfuzzy")

from driver_fatigue.domain.fatigue_index import FatigueInputs
from driver_fatigue.infrastructure.fatigue_inference.fuzzy import (
    FuzzyIndexEvaluator,
)


@pytest.fixture(scope="module")
def evaluator():
    return FuzzyIndexEvaluator()


def _inputs(**over) -> FatigueInputs:
    base = dict(
        ear_norm=0.85, mar_norm=0.10, head_drop_frames=0,
        consecutive_eyes_closed=0, bpm=75.0, steering_noise=0.10,
        hours_driving=1.0, hour_of_day=10.0,
    )
    base.update(over)
    return FatigueInputs(**base)


def test_normal_baseline_low_index(evaluator):
    out = evaluator.compute(_inputs())
    assert out.value < 35, f"esperado normal, veio {out.value:.1f}"
    assert out.severity == "normal"
