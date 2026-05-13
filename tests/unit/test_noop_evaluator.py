from driver_fatigue.domain.fatigue_index import FatigueInputs
from driver_fatigue.infrastructure.fatigue_inference.noop import NoOpIndexEvaluator


def test_noop_returns_zero_index():
    ev = NoOpIndexEvaluator()
    out = ev.compute(FatigueInputs(0.8, 0.1, 0, 0, 75.0, 0.1, 1.0, 10.0))
    assert out.value == 0.0
    assert out.severity == "normal"
    assert out.explain == "indice de fadiga desabilitado"
