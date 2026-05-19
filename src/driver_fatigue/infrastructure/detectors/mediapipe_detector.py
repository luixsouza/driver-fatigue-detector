from __future__ import annotations

from pathlib import Path

import cv2
import mediapipe as mp
import mediapipe.tasks as mp_tasks

from driver_fatigue.domain.entities import FaceLandmarks, Frame, Point

_DEFAULT_MODEL = Path(__file__).resolve().parents[4] / "models" / "face_landmarker.task"

LEFT_EYE_EAR_INDICES  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_EAR_INDICES = [362, 385, 387, 263, 373, 380]
LEFT_IRIS_INDICES  = [468, 469, 470, 471, 472]
RIGHT_IRIS_INDICES = [473, 474, 475, 476, 477]
MOUTH_OUTER_MAR_INDICES = [61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91]
MOUTH_INNER_INDICES = [78, 81, 13, 311, 308, 402, 14, 178]
FACE_OVAL_INDICES = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]


class MediapipeFaceDetector:
    def __init__(
        self,
        model_path: str | Path | None = None,
        max_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        detect_width: int = 640,
    ) -> None:
        resolved_model = Path(model_path) if model_path else _DEFAULT_MODEL
        base_options = mp_tasks.BaseOptions(model_asset_path=str(resolved_model))
        # RunningMode.VIDEO reusa o tracker entre frames (~2x mais rápido que
        # IMAGE em CPU). detect_for_video exige timestamp ms monotonicamente
        # crescente — usamos um contador interno pra garantir.
        options = mp_tasks.vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_tasks.vision.RunningMode.VIDEO,
            num_faces=max_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = mp_tasks.vision.FaceLandmarker.create_from_options(options)
        self._last_ts_ms = 0
        # Detecção em resolução reduzida: landmarks vêm normalizados (0..1),
        # então remapeamos pro tamanho original sem perder precisão visual.
        # 640px é suficiente pro modelo, e cai o custo de detecção em ~3x.
        self._detect_width = max(160, detect_width)

    def detect(self, frame: Frame) -> list[FaceLandmarks]:
        h, w = frame.image.shape[:2]
        if w > self._detect_width:
            scale = self._detect_width / float(w)
            small = cv2.resize(
                frame.image,
                (self._detect_width, int(h * scale)),
                interpolation=cv2.INTER_LINEAR,
            )
        else:
            small = frame.image
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # Timestamp monotonicamente crescente; usa o do frame se válido,
        # cai pra contador interno se não (frame.timestamp pode ser float
        # monotonic_seconds que repetiria entre execuções).
        ts_ms = max(self._last_ts_ms + 1, int(frame.timestamp * 1000))
        self._last_ts_ms = ts_ms
        results = self._landmarker.detect_for_video(mp_image, ts_ms)
        if not results.face_landmarks:
            return []

        out: list[FaceLandmarks] = []
        for face in results.face_landmarks:
            pts = [Point(x=lm.x * w, y=lm.y * h) for lm in face]
            out.append(FaceLandmarks(
                left_eye_contour=tuple(pts[i] for i in LEFT_EYE_EAR_INDICES),
                right_eye_contour=tuple(pts[i] for i in RIGHT_EYE_EAR_INDICES),
                left_iris=tuple(pts[i] for i in LEFT_IRIS_INDICES) if len(pts) > 472 else None,
                right_iris=tuple(pts[i] for i in RIGHT_IRIS_INDICES) if len(pts) > 477 else None,
                mouth_outer=tuple(pts[i] for i in MOUTH_OUTER_MAR_INDICES),
                mouth_inner=tuple(pts[i] for i in MOUTH_INNER_INDICES),
                face_oval=tuple(pts[i] for i in FACE_OVAL_INDICES),
            ))
        return out

    def close(self) -> None:
        self._landmarker.close()
