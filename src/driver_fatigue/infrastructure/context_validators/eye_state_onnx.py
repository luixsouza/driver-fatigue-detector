"""EyeStateContextValidator — confirma sonolência por estado dos olhos.

Modos de operação:

1. **PERCLOS-only** (sem modelo ONNX): mantém um buffer dos últimos
   `perclos_window_seconds` segundos com a flag eyes_closed (derivada do EAR
   já calculado pelo evaluator). Confirma drowsy se PERCLOS >= threshold.
   Funciona sem dependência extra — é o default seguro.

2. **ONNX**: se `model_path` apontar pra um arquivo válido E `onnxruntime`
   estiver instalado, usa o modelo pra classificar o crop dos olhos do
   frame atual. Combina com PERCLOS via AND lógico — drowsy quando ambos
   concordam.

Sem modelo, sem ONNX, sem rede. 100% local e gratuito.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.value_objects import ContextVerdict
from driver_fatigue.infrastructure.context_validators.perclos import PerclosBuffer

_log = logging.getLogger("driver_fatigue.context.eye_state")


class EyeStateContextValidator:
    def __init__(
        self,
        model_path: Path | None = None,
        perclos_window_seconds: float = 60.0,
        perclos_threshold: float = 0.4,
        ear_close_threshold: float | None = None,
        min_perclos_samples: int = 30,
    ) -> None:
        if not 0.0 < perclos_threshold < 1.0:
            raise ValueError("perclos_threshold deve estar em (0,1)")
        self._perclos = PerclosBuffer(window_seconds=perclos_window_seconds)
        self._perclos_threshold = perclos_threshold
        self._ear_close_threshold = ear_close_threshold
        self._min_perclos_samples = max(min_perclos_samples, 1)
        self._session = None
        if model_path is not None and Path(model_path).exists():
            try:
                import onnxruntime as ort
                self._session = ort.InferenceSession(
                    str(model_path),
                    providers=["CPUExecutionProvider"],
                )
                _log.info("EyeState ONNX carregado de %s", model_path)
            except ImportError:
                _log.warning("onnxruntime não instalado; modo PERCLOS-only")
            except Exception as exc:
                _log.warning("Falha ao carregar ONNX (%s); modo PERCLOS-only", exc)

    def confirm_drowsy(
        self,
        frame: Frame,
        landmarks: FaceLandmarks,
        state: FatigueState,
    ) -> ContextVerdict:
        eyes_closed_now = self._eyes_closed(state)
        self._perclos.add(frame.timestamp, eyes_closed_now)
        ratio = self._perclos.ratio()

        if self._perclos.sample_count() < self._min_perclos_samples:
            # Sem amostras suficientes: confia na heurística (confirma).
            return ContextVerdict(
                drowsy=True, confidence=0.6,
                reason=f"insufficient PERCLOS samples ({self._perclos.sample_count()})",
            )

        perclos_says_drowsy = ratio >= self._perclos_threshold

        if self._session is None:
            return self._verdict_from_perclos(perclos_says_drowsy, ratio)

        onnx_says_drowsy, onnx_conf = self._classify_with_onnx(frame, landmarks)
        drowsy = perclos_says_drowsy and onnx_says_drowsy
        confidence = min(1.0, max(0.0, onnx_conf if drowsy else 1.0 - onnx_conf))
        reason = (
            f"PERCLOS {ratio:.2f} + ONNX {'drowsy' if onnx_says_drowsy else 'awake'}"
        )
        return ContextVerdict(drowsy=drowsy, confidence=confidence, reason=reason)

    def _eyes_closed(self, state: FatigueState) -> bool:
        if self._ear_close_threshold is not None:
            return state.ear < self._ear_close_threshold
        baseline = state.baseline
        if baseline.sample_count >= 30 and baseline.ear_rest > 0:
            return state.ear < baseline.ear_rest * 0.75
        return state.ear < 0.22

    def _verdict_from_perclos(self, drowsy: bool, ratio: float) -> ContextVerdict:
        if drowsy:
            return ContextVerdict(
                drowsy=True,
                confidence=min(1.0, 0.6 + (ratio - self._perclos_threshold)),
                reason=f"PERCLOS {ratio:.2f} >= {self._perclos_threshold:.2f}",
            )
        return ContextVerdict(
            drowsy=False,
            confidence=min(1.0, 0.6 + (self._perclos_threshold - ratio)),
            reason=f"PERCLOS {ratio:.2f} < {self._perclos_threshold:.2f}",
        )

    def _classify_with_onnx(
        self,
        frame: Frame,
        landmarks: FaceLandmarks,
    ) -> tuple[bool, float]:
        try:
            left_crop = self._eye_crop(frame, landmarks.left_eye_contour)
            right_crop = self._eye_crop(frame, landmarks.right_eye_contour)
            left_score = self._infer(left_crop)
            right_score = self._infer(right_crop)
            avg = (left_score + right_score) / 2.0
            return avg > 0.5, abs(avg - 0.5) * 2
        except Exception as exc:
            _log.warning("Inferência ONNX falhou (%s); ignorando", exc)
            return True, 0.5

    def _eye_crop(self, frame: Frame, eye: tuple[Point, ...]) -> np.ndarray:
        h, w = frame.image.shape[:2]
        xs = [p.x for p in eye]
        ys = [p.y for p in eye]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        size = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.4
        x0 = max(0, int(cx - size / 2))
        y0 = max(0, int(cy - size / 2))
        x1 = min(w, int(cx + size / 2))
        y1 = min(h, int(cy + size / 2))
        if x1 <= x0 or y1 <= y0:
            raise ValueError("crop vazio")
        crop = frame.image[y0:y1, x0:x1]
        import cv2
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (24, 24), interpolation=cv2.INTER_AREA)
        return resized.astype(np.float32) / 255.0

    def _infer(self, crop_24x24: np.ndarray) -> float:
        x = crop_24x24[np.newaxis, np.newaxis, :, :]
        outputs = self._session.run(None, {self._session.get_inputs()[0].name: x})
        out = np.asarray(outputs[0]).flatten()
        if out.size == 1:
            return float(out[0])
        if out.size == 2:
            exps = np.exp(out - out.max())
            probs = exps / exps.sum()
            return float(probs[1])
        return float(out.max())
