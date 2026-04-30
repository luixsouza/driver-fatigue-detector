from __future__ import annotations

import logging

import httpx

from driver_fatigue.domain.entities import FatigueEvent

_log = logging.getLogger("driver_fatigue.alerts.http")


class HttpWebhookSink:
    """Posta eventos como JSON em um webhook HTTP."""

    def __init__(
        self,
        url: str,
        bearer_token: str | None = None,
        timeout_seconds: float = 3.0,
        api_key: str | None = None,
    ) -> None:
        self._url = url
        headers = {"Content-Type": "application/json"}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.Client(
            headers=headers,
            timeout=timeout_seconds,
        )

    def notify(self, event: FatigueEvent) -> None:
        payload = {
            "event": "fatigue_alert",
            "timestamp": event.timestamp,
            "frame_index": event.frame_index,
            "ear": event.state.ear,
            "mar": event.state.mar,
            "severity": event.state.severity,
            "consecutive_frames": event.state.consecutive_frames,
        }
        self._post(payload)

    def on_recovery(self, frame_index: int) -> None:
        payload = {
            "event": "fatigue_recovery",
            "timestamp": 0.0,
            "frame_index": frame_index,
        }
        self._post(payload)

    def publish_state(self, frame, state) -> None:
        """Heartbeat pro dashboard: estado atual a cada N frames."""
        baseline = state.baseline
        payload = {
            "event": "state",
            "timestamp": frame.timestamp,
            "frame_index": frame.index,
            "ear": state.ear,
            "mar": state.mar,
            "severity": state.severity,
            "consecutive_frames": state.consecutive_frames,
            "calibrating": (
                baseline.sample_count > 0 and baseline.sample_count < 30
            ),
            "calibration_progress": min(1.0, baseline.sample_count / 45.0),
            "quality_ok": state.quality.trustworthy,
            "quality_reason": state.quality.reason,
        }
        self._post(payload)

    def _post(self, payload: dict) -> None:
        try:
            response = self._client.post(self._url, json=payload)
            if response.status_code >= 500:
                _log.warning("webhook retornou %d", response.status_code)
        except httpx.HTTPError as e:
            _log.warning("webhook falhou: %s", e)

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass
