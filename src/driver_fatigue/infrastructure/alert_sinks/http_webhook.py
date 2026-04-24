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
    ) -> None:
        self._url = url
        headers = {"Content-Type": "application/json"}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
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
