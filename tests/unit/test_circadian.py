import pytest

from driver_fatigue.domain.fatigue_index import circadian_risk


@pytest.mark.parametrize("hour,expected_range", [
    (3.0,  (0.85, 1.0)),   # madrugada profunda
    (4.5,  (0.85, 1.0)),
    (12.0, (0.0, 0.2)),    # meio-dia
    (15.0, (0.5, 0.7)),    # pós-almoço
    (20.0, (0.0, 0.2)),    # noite cedo
    (0.0,  (0.0, 0.5)),    # transição
])
def test_circadian_risk_in_expected_ranges(hour, expected_range):
    low, high = expected_range
    risk = circadian_risk(hour)
    assert low <= risk <= high, f"hour={hour} risk={risk:.2f} esperado em [{low},{high}]"


def test_circadian_risk_is_continuous_at_transitions():
    # transições 30min: 01:30→02:00 deve subir suavemente
    r1 = circadian_risk(1.5)
    r2 = circadian_risk(2.0)
    assert r2 > r1
    assert r2 - r1 < 0.5  # nao salta abrupto


def test_circadian_risk_clamps_input():
    assert circadian_risk(-1.0) == circadian_risk(0.0)
    assert circadian_risk(25.0) == circadian_risk(23.99)
