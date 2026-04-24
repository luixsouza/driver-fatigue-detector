from __future__ import annotations

import json
import logging

import paho.mqtt.client as mqtt

from driver_fatigue.domain.entities import FatigueEvent

_log = logging.getLogger("driver_fatigue.alerts.mqtt")


class MqttSink:
    """Publica eventos como JSON em um broker MQTT com QoS 1."""

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        topic: str = "driver_fatigue/events",
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
        connect_timeout_seconds: float = 3.0,
    ) -> None:
        self._broker = broker
        self._port = port
        self._topic = topic
        self._connected = False

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1,
            client_id=client_id or "",
        )
        if username is not None:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        try:
            self._client.connect(broker, port, keepalive=int(connect_timeout_seconds * 10))
            self._client.loop_start()
            self._connected = True
        except Exception as e:
            _log.warning("falha ao conectar MQTT %s:%d — %s", broker, port, e)

    def _on_connect(self, client, userdata, flags, rc):
        self._connected = (rc == 0)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False

    def _ensure_connected(self) -> None:
        if self._connected:
            return
        try:
            self._client.reconnect()
            self._connected = True
        except Exception as e:
            _log.warning("reconexao MQTT falhou: %s", e)

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
        self._publish(payload)

    def on_recovery(self, frame_index: int) -> None:
        payload = {
            "event": "fatigue_recovery",
            "timestamp": 0.0,
            "frame_index": frame_index,
        }
        self._publish(payload)

    def _publish(self, payload: dict) -> None:
        self._ensure_connected()
        try:
            self._client.publish(self._topic, json.dumps(payload), qos=1)
        except Exception as e:
            _log.warning("publish MQTT falhou: %s", e)

    def __del__(self):
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass
