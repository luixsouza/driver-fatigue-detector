import numpy as np

from driver_fatigue.domain.entities import FatigueState, Frame
from driver_fatigue.infrastructure.presenters.headless import HeadlessPresenter


def _frame():
    return Frame(image=np.zeros((10, 10, 3), dtype=np.uint8), timestamp=0.0, index=0)


class TestHeadlessPresenter:
    def test_present_is_noop(self):
        p = HeadlessPresenter()
        p.present(_frame(), [], FatigueState.initial())

    def test_should_stop_defaults_false(self):
        p = HeadlessPresenter()
        assert p.should_stop() is False

    def test_request_stop_method(self):
        p = HeadlessPresenter()
        p.request_stop()
        assert p.should_stop() is True

    def test_close_is_idempotent(self):
        p = HeadlessPresenter()
        p.close()
        p.close()
