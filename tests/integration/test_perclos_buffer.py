import pytest

from driver_fatigue.infrastructure.context_validators.perclos import PerclosBuffer


class TestPerclosBuffer:
    def test_empty_ratio_is_zero(self):
        b = PerclosBuffer(window_seconds=10.0)
        assert b.ratio() == 0.0
        assert b.sample_count() == 0

    def test_ratio_with_mixed_samples(self):
        b = PerclosBuffer(window_seconds=10.0)
        for t, closed in [(0, True), (1, False), (2, True), (3, True)]:
            b.add(float(t), closed)
        assert b.sample_count() == 4
        assert b.ratio() == pytest.approx(0.75)

    def test_old_samples_dropped(self):
        b = PerclosBuffer(window_seconds=5.0)
        b.add(0.0, True)
        b.add(1.0, True)
        b.add(2.0, False)
        b.add(10.0, False)  # dropa 0,1,2 (cutoff 10-5=5)
        assert b.sample_count() == 1
        assert b.ratio() == 0.0

    def test_invalid_window(self):
        with pytest.raises(ValueError):
            PerclosBuffer(window_seconds=0)
        with pytest.raises(ValueError):
            PerclosBuffer(window_seconds=-1)

    def test_window_keeps_boundary_samples(self):
        b = PerclosBuffer(window_seconds=5.0)
        b.add(0.0, True)
        b.add(5.0, True)
        # cutoff = 5-5=0; 0.0 está em t<cutoff? não (0<0 falso), mantém
        assert b.sample_count() == 2
