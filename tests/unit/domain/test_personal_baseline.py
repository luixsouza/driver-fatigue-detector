from driver_fatigue.domain.value_objects import PersonalBaseline


class TestPersonalBaseline:
    def test_empty_is_not_calibrated(self):
        b = PersonalBaseline.empty()
        assert b.sample_count == 0
        assert not b.is_calibrated(60)

    def test_absorb_updates_means(self):
        b = PersonalBaseline.empty()
        b = b.absorb(0.30, 0.20)
        b = b.absorb(0.32, 0.18)
        b = b.absorb(0.28, 0.22)
        assert abs(b.ear_rest - 0.30) < 1e-6
        assert abs(b.mar_rest - 0.20) < 1e-6
        assert b.sample_count == 3
        assert b.ear_std > 0
        assert b.mar_std > 0

    def test_calibration_threshold(self):
        b = PersonalBaseline.empty()
        for _ in range(60):
            b = b.absorb(0.30, 0.20)
        assert b.is_calibrated(60)
        assert b.ear_std == 0.0  # constantes → variância zero

    def test_warmup_zero_always_calibrated_after_one_sample(self):
        b = PersonalBaseline.empty().absorb(0.3, 0.2)
        assert b.is_calibrated(0)

    def test_welford_variance_matches_formula(self):
        import statistics
        b = PersonalBaseline.empty()
        ear_samples = [0.30, 0.32, 0.28, 0.31, 0.29]
        for v in ear_samples:
            b = b.absorb(v, 0.2)
        expected = statistics.stdev(ear_samples)
        assert abs(b.ear_std - expected) < 1e-9
