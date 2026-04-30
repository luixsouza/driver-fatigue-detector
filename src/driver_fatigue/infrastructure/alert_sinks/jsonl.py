from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from driver_fatigue.domain.entities import FatigueEvent

_log = logging.getLogger("driver_fatigue.alerts.jsonl")


class JsonlEventSink:
    """Persiste eventos em arquivo JSONL append-only.

    Cada linha é um JSON com métricas numéricas — sem imagem, sem
    identificação biométrica. Serve como evidência auditável da POC e
    como fonte para análise offline. Veja docs/PRIVACY.md.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def notify(self, event: FatigueEvent) -> None:
        baseline = event.state.baseline
        record = {
            "event": "fatigue_alert",
            "timestamp": event.timestamp,
            "wall_clock": time.time(),
            "frame_index": event.frame_index,
            "ear": event.state.ear,
            "mar": event.state.mar,
            "severity": event.state.severity,
            "consecutive_frames": event.state.consecutive_frames,
            "baseline_ear": baseline.ear_rest,
            "baseline_mar": baseline.mar_rest,
            "calibrated": baseline.sample_count >= 30,
            "quality_ok": event.state.quality.trustworthy,
            "quality_reason": event.state.quality.reason,
        }
        self._append(record)

    def on_recovery(self, frame_index: int) -> None:
        record = {
            "event": "fatigue_recovery",
            "wall_clock": time.time(),
            "frame_index": frame_index,
        }
        self._append(record)

    def _append(self, record: dict) -> None:
        line = json.dumps(record, separators=(",", ":")) + "\n"
        try:
            with self._lock, self._path.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError as exc:
            _log.warning("falha ao gravar evento em %s: %s", self._path, exc)
