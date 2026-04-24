import numpy as np

from driver_fatigue.domain.entities import FatigueState, Frame
from driver_fatigue.infrastructure.presenters.composite import CompositePresenter


def _frame():
    return Frame(image=np.zeros((10, 10, 3), dtype=np.uint8), timestamp=0.0, index=0)


class SpyPresenter:
    def __init__(self, stop: bool = False, raise_on_close: bool = False):
        self.presented = 0
        self.closed = False
        self._stop = stop
        self._raise = raise_on_close

    def present(self, frame, lm, state):
        self.presented += 1

    def should_stop(self):
        return self._stop

    def close(self):
        self.closed = True
        if self._raise:
            raise RuntimeError("boom")


class TestCompositePresenter:
    def test_present_calls_all(self):
        a, b = SpyPresenter(), SpyPresenter()
        c = CompositePresenter(a, b)
        c.present(_frame(), [], FatigueState.initial())
        assert a.presented == 1 and b.presented == 1

    def test_should_stop_is_or(self):
        a = SpyPresenter(stop=False)
        b = SpyPresenter(stop=True)
        c = CompositePresenter(a, b)
        assert c.should_stop() is True

    def test_close_propagates_even_if_one_raises(self):
        a = SpyPresenter(raise_on_close=True)
        b = SpyPresenter()
        c = CompositePresenter(a, b)
        c.close()
        assert a.closed is True and b.closed is True
