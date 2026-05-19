from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FatigueThresholds:
    ear_threshold: float = 0.25
    mar_threshold: float = 0.60
    consecutive_frames: int = 20
    warning_ratio: float = 0.85
    # Defaults compatíveis com Fase 1 (sem histerese / cooldown);
    # AppSettings aplica defaults mais robustos para produção.
    recovery_frames: int = 0
    min_alert_duration_frames: int = 0
    alarm_cooldown_seconds: float = 0.0
    yawn_window_frames: int = 45
    yawn_stability_max: float = 1e9  # default permissivo: qualquer std passa
    head_drop_pitch_deg: float = 25.0       # cabeça caindo a partir desse pitch
    head_drop_frames_threshold: int = 30    # frames sustentados pra contar como sonolência

    def __post_init__(self) -> None:
        if not 0.0 < self.warning_ratio <= 1.0:
            raise ValueError("warning_ratio deve estar em (0, 1]")
        if self.consecutive_frames < 0:
            raise ValueError("consecutive_frames não pode ser negativo")
        if self.ear_threshold <= 0:
            raise ValueError("ear_threshold deve ser positivo")
        if self.mar_threshold <= 0:
            raise ValueError("mar_threshold deve ser positivo")
        if self.recovery_frames < 0:
            raise ValueError("recovery_frames não pode ser negativo")
        if self.min_alert_duration_frames < 0:
            raise ValueError("min_alert_duration_frames não pode ser negativo")
        if self.alarm_cooldown_seconds < 0:
            raise ValueError("alarm_cooldown_seconds não pode ser negativo")
        if self.yawn_window_frames <= 0:
            raise ValueError("yawn_window_frames deve ser positivo")
        if self.yawn_stability_max < 0:
            raise ValueError("yawn_stability_max não pode ser negativo")


@dataclass(frozen=True, slots=True)
class CalibrationSettings:
    enabled: bool = True
    warmup_frames: int = 60
    ear_close_ratio: float = 0.75
    mar_open_zscore: float = 2.5

    def __post_init__(self) -> None:
        if self.warmup_frames < 0:
            raise ValueError("warmup_frames não pode ser negativo")
        if not 0.0 < self.ear_close_ratio < 1.0:
            raise ValueError("ear_close_ratio deve estar em (0, 1)")
        if self.mar_open_zscore <= 0:
            raise ValueError("mar_open_zscore deve ser positivo")


@dataclass(frozen=True, slots=True)
class PersonalBaseline:
    """Baseline EAR/MAR aprendido por usuário durante o warmup.

    Permite thresholds relativos: o que é "olho fechado" depende do EAR de
    repouso da pessoa (formato do olho, óculos, iluminação ambiente).
    """
    ear_rest: float = 0.0
    mar_rest: float = 0.0
    ear_std: float = 0.0
    mar_std: float = 0.0
    # Pitch de repouso da pessoa (geometria do rosto, postura natural).
    # `estimate_pitch_deg` tem viés não-zero pra rostos frontais (olhos ficam
    # acima do centro do face_oval), então threshold de cabeceio precisa ser
    # relativo a esse baseline pra não disparar com cara reta.
    pitch_rest: float = 0.0
    sample_count: int = 0

    @classmethod
    def empty(cls) -> "PersonalBaseline":
        return cls()

    def is_calibrated(self, warmup_frames: int) -> bool:
        return self.sample_count >= max(warmup_frames, 1)

    def absorb(self, ear: float, mar: float, pitch_deg: float = 0.0) -> "PersonalBaseline":
        """Atualiza médias e desvios via algoritmo de Welford (online)."""
        n = self.sample_count + 1
        ear_mean = self.ear_rest + (ear - self.ear_rest) / n
        mar_mean = self.mar_rest + (mar - self.mar_rest) / n
        pitch_mean = self.pitch_rest + (pitch_deg - self.pitch_rest) / n
        if n > 1:
            ear_var = ((n - 2) * self.ear_std**2
                       + (ear - self.ear_rest) * (ear - ear_mean)) / (n - 1)
            mar_var = ((n - 2) * self.mar_std**2
                       + (mar - self.mar_rest) * (mar - mar_mean)) / (n - 1)
            ear_std = max(ear_var, 0.0) ** 0.5
            mar_std = max(mar_var, 0.0) ** 0.5
        else:
            ear_std = 0.0
            mar_std = 0.0
        return PersonalBaseline(
            ear_rest=ear_mean,
            mar_rest=mar_mean,
            ear_std=ear_std,
            mar_std=mar_std,
            pitch_rest=pitch_mean,
            sample_count=n,
        )


QualityIssue = str


@dataclass(frozen=True, slots=True)
class FrameQuality:
    """Avaliação de confiabilidade do frame para fins de detecção de fadiga.

    Frames pouco confiáveis (rosto torto, longe, fora do quadro, baixa
    confiança do detector) NÃO devem alimentar o evaluator — alimentariam
    falsos positivos e arruinariam a calibração.
    """
    trustworthy: bool
    reason: QualityIssue = ""
    head_yaw_deg: float = 0.0
    head_pitch_deg: float = 0.0
    face_area_ratio: float = 0.0
    detector_confidence: float = 1.0

    @classmethod
    def trusted(
        cls,
        *,
        head_yaw_deg: float = 0.0,
        head_pitch_deg: float = 0.0,
        face_area_ratio: float = 1.0,
        detector_confidence: float = 1.0,
    ) -> "FrameQuality":
        return cls(
            trustworthy=True,
            reason="",
            head_yaw_deg=head_yaw_deg,
            head_pitch_deg=head_pitch_deg,
            face_area_ratio=face_area_ratio,
            detector_confidence=detector_confidence,
        )

    @classmethod
    def untrusted(cls, reason: QualityIssue, **kwargs: float) -> "FrameQuality":
        return cls(trustworthy=False, reason=reason, **kwargs)


@dataclass(frozen=True, slots=True)
class FrameQualityPolicy:
    # Defaults permissivos: comportamento Fase 1.
    # Use FrameQualityPolicy.production() para defaults robustos.
    min_face_confidence: float = 0.0
    min_face_area_ratio: float = 0.0
    max_head_yaw_deg: float = 90.0
    max_head_pitch_deg: float = 90.0

    @classmethod
    def production(cls) -> "FrameQualityPolicy":
        return cls(
            min_face_confidence=0.5,
            min_face_area_ratio=0.05,
            max_head_yaw_deg=35.0,
            max_head_pitch_deg=25.0,
        )

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_face_confidence <= 1.0:
            raise ValueError("min_face_confidence deve estar em [0, 1]")
        if not 0.0 <= self.min_face_area_ratio <= 1.0:
            raise ValueError("min_face_area_ratio deve estar em [0, 1]")
        if self.max_head_yaw_deg <= 0:
            raise ValueError("max_head_yaw_deg deve ser positivo")
        if self.max_head_pitch_deg <= 0:
            raise ValueError("max_head_pitch_deg deve ser positivo")

    def evaluate(
        self,
        *,
        head_yaw_deg: float,
        head_pitch_deg: float,
        face_area_ratio: float,
        detector_confidence: float,
    ) -> FrameQuality:
        if detector_confidence < self.min_face_confidence:
            return FrameQuality.untrusted(
                reason=f"low confidence ({detector_confidence:.2f})",
                head_yaw_deg=head_yaw_deg, head_pitch_deg=head_pitch_deg,
                face_area_ratio=face_area_ratio,
                detector_confidence=detector_confidence,
            )
        if face_area_ratio < self.min_face_area_ratio:
            return FrameQuality.untrusted(
                reason=f"face too small ({face_area_ratio:.3f})",
                head_yaw_deg=head_yaw_deg, head_pitch_deg=head_pitch_deg,
                face_area_ratio=face_area_ratio,
                detector_confidence=detector_confidence,
            )
        if abs(head_yaw_deg) > self.max_head_yaw_deg:
            return FrameQuality.untrusted(
                reason=f"head yaw {head_yaw_deg:.0f} deg",
                head_yaw_deg=head_yaw_deg, head_pitch_deg=head_pitch_deg,
                face_area_ratio=face_area_ratio,
                detector_confidence=detector_confidence,
            )
        if abs(head_pitch_deg) > self.max_head_pitch_deg:
            return FrameQuality.untrusted(
                reason=f"head pitch {head_pitch_deg:.0f} deg",
                head_yaw_deg=head_yaw_deg, head_pitch_deg=head_pitch_deg,
                face_area_ratio=face_area_ratio,
                detector_confidence=detector_confidence,
            )
        return FrameQuality.trusted(
            head_yaw_deg=head_yaw_deg, head_pitch_deg=head_pitch_deg,
            face_area_ratio=face_area_ratio,
            detector_confidence=detector_confidence,
        )


@dataclass(frozen=True, slots=True)
class ContextVerdict:
    """Veredito de um ContextValidator opcional sobre se o frame
    realmente mostra sonolência (chamado só quando a heurística já entrou em alert).
    """
    drowsy: bool
    confidence: float = 1.0
    reason: str = ""
    latency_ms: float = 0.0

    @classmethod
    def confirm(cls, reason: str = "confirmed") -> "ContextVerdict":
        return cls(drowsy=True, confidence=1.0, reason=reason)

    @classmethod
    def reject(cls, reason: str = "rejected") -> "ContextVerdict":
        return cls(drowsy=False, confidence=1.0, reason=reason)
