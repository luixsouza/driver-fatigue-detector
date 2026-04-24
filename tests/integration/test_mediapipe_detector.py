import cv2
import pytest

from driver_fatigue.domain.entities import Frame
from driver_fatigue.infrastructure.detectors.mediapipe_detector import (
    MediapipeFaceDetector,
)


@pytest.fixture
def frames_from_test_video(test_video_path):
    cap = cv2.VideoCapture(str(test_video_path))
    assert cap.isOpened()
    frames = []
    for i in range(10):
        ok, img = cap.read()
        if not ok:
            break
        frames.append(Frame(image=img, timestamp=float(i), index=i))
    cap.release()
    return frames


class TestMediapipeFaceDetector:
    def test_detects_at_least_one_face_in_sample(self, frames_from_test_video):
        det = MediapipeFaceDetector()
        try:
            detections = [det.detect(f) for f in frames_from_test_video]
        finally:
            det.close()
        hits = sum(1 for d in detections if d)
        assert hits >= len(frames_from_test_video) // 2

    def test_returned_landmarks_have_expected_arities(self, frames_from_test_video):
        det = MediapipeFaceDetector()
        try:
            for f in frames_from_test_video:
                for lm in det.detect(f):
                    assert len(lm.left_eye_contour) == 6
                    assert len(lm.right_eye_contour) == 6
                    assert len(lm.mouth_outer) == 12
                    assert len(lm.mouth_inner) == 8
                    assert len(lm.face_oval) == 36
                    if lm.left_iris is not None:
                        assert len(lm.left_iris) == 5
                        assert len(lm.right_iris) == 5
                    return
        finally:
            det.close()
        pytest.fail("nenhum rosto detectado — teste inconclusivo")
