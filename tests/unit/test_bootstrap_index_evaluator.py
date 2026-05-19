from driver_fatigue.bootstrap import _build_index_evaluator
from driver_fatigue.infrastructure.fatigue_inference.noop import NoOpIndexEvaluator
from driver_fatigue.config.settings import AppSettings, FatigueIndexSettings


def test_disabled_returns_noop():
    s = AppSettings(fatigue_index=FatigueIndexSettings(enabled=False))
    ev = _build_index_evaluator(s)
    assert isinstance(ev, NoOpIndexEvaluator)


def test_enabled_returns_fuzzy_when_available():
    import pytest
    pytest.importorskip("skfuzzy")
    from driver_fatigue.infrastructure.fatigue_inference.fuzzy import FuzzyIndexEvaluator
    s = AppSettings()
    ev = _build_index_evaluator(s)
    assert isinstance(ev, FuzzyIndexEvaluator)
