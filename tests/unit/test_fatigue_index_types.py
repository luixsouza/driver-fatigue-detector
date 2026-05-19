from driver_fatigue.domain.fatigue_index import (
    FatigueIndex,
    FatigueInputs,
    IndexEvaluator,
)


def test_inputs_are_constructible():
    inp = FatigueInputs(
        ear_norm=0.8, mar_norm=0.1, head_drop_frames=0,
        consecutive_eyes_closed=0, bpm=75.0, steering_noise=0.1,
        hours_driving=1.0, hour_of_day=10.0,
    )
    assert inp.bpm == 75.0


def test_index_empty_factory():
    idx = FatigueIndex.empty()
    assert idx.value == 0.0
    assert idx.severity == "normal"
    assert idx.top_contributors == ()
    assert idx.critical is False


def test_index_evaluator_is_protocol():
    # Protocol — qualquer obj com .compute(inputs) -> FatigueIndex satisfaz
    class _Fake:
        def compute(self, inputs):
            return FatigueIndex.empty()
    f: IndexEvaluator = _Fake()
    assert isinstance(f.compute(FatigueInputs(0,0,0,0,0,0,0,0)), FatigueIndex)
