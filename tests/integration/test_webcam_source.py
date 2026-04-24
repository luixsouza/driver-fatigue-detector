import cv2
import pytest

from driver_fatigue.infrastructure.video_sources.webcam import WebcamVideoSource


def _webcam_available() -> bool:
    cap = cv2.VideoCapture(0)
    ok = cap.isOpened()
    cap.release()
    return ok


pytestmark = pytest.mark.skipif(
    not _webcam_available(),
    reason="webcam 0 indisponível",
)


class TestWebcamVideoSource:
    def test_reads_a_frame(self):
        src = WebcamVideoSource(device_index=0)
        try:
            frame = src.read()
            assert frame is not None
            assert frame.image.shape[2] == 3
            assert frame.index == 0
            next_frame = src.read()
            assert next_frame.index == 1
        finally:
            src.release()

    def test_release_is_idempotent(self):
        src = WebcamVideoSource(device_index=0)
        src.release()
        src.release()
