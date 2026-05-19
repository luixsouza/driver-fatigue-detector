"""Testes de comportamento do motor fuzzy.

Cobrimos cada caso de fadiga prototipico do spec. Os limites de severity
sao: < 35 normal, 35-60 warning, 60-80 alert, >= 80 alert+critical.
"""
import pytest

skfuzzy = pytest.importorskip("skfuzzy")

from driver_fatigue.domain.fatigue_index import FatigueInputs  # noqa: E402
from driver_fatigue.infrastructure.index_evaluators.fuzzy import (  # noqa: E402
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


def test_eyes_closed_plus_head_drop_triggers_alert(evaluator):
    # R1: eyes_closed + head_drop = alerta (>= 60)
    out = evaluator.compute(_inputs(
        ear_norm=0.10, head_drop_frames=20,
    ))
    assert out.value >= 60, f"esperado alert, veio {out.value:.1f}"
    assert out.severity == "alert"


def test_eyes_closed_plus_yawn_is_critical(evaluator):
    # R2: critico (>=80)
    out = evaluator.compute(_inputs(
        ear_norm=0.10, mar_norm=0.85,
    ))
    assert out.value >= 75, f"esperado critico, veio {out.value:.1f}"
    assert out.critical or out.severity == "alert"


def test_low_bpm_with_partial_eyes_triggers_alert(evaluator):
    # R4: bpm baixo + olhos nao-abertos
    out = evaluator.compute(_inputs(
        bpm=45.0, ear_norm=0.50,
    ))
    assert out.value >= 50


def test_drowsy_night_scenario_is_critical(evaluator):
    # R12: tempo longo + bpm baixo + olhos parciais + circadiano vale
    out = evaluator.compute(_inputs(
        ear_norm=0.40, mar_norm=0.30, bpm=48.0,
        hours_driving=8.0, hour_of_day=3.5,
        steering_noise=0.60,
    ))
    assert out.value >= 70, f"cenario noturno: {out.value:.1f}"


def test_talking_not_yawning_stays_normal(evaluator):
    # R9: anti-FP: motorista falando (mar medio, ear normal) nao deve gerar alert
    out = evaluator.compute(_inputs(
        ear_norm=0.80, mar_norm=0.45,
    ))
    assert out.value < 50, f"falando virou alert: {out.value:.1f}"


def test_heavy_head_drop_is_critical(evaluator):
    # R10
    out = evaluator.compute(_inputs(
        head_drop_frames=45,
    ))
    assert out.value >= 70


def test_explain_text_non_empty_when_active(evaluator):
    out = evaluator.compute(_inputs(
        ear_norm=0.10, head_drop_frames=20,
    ))
    assert out.explain != ""
    assert len(out.top_contributors) >= 1
