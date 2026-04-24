import json
from unittest.mock import MagicMock, patch

from driver_fatigue.domain.entities import FatigueEvent, FatigueState


def _alert_event():
    return FatigueEvent(
        timestamp=1.5,
        state=FatigueState(
            ear=0.18, mar=0.52, consecutive_frames=20,
            is_fatigued=True, is_yawning=False, severity="alert",
        ),
        frame_index=100,
    )


class TestMqttSink:
    @patch("driver_fatigue.infrastructure.alert_sinks.mqtt.mqtt")
    def test_notify_publishes_json_payload(self, paho_mock):
        from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink

        client_instance = MagicMock()
        paho_mock.Client.return_value = client_instance

        sink = MqttSink(broker="mqtt.example", topic="driver_fatigue/events")
        sink.notify(_alert_event())

        assert client_instance.publish.called
        call = client_instance.publish.call_args
        assert call.args[0] == "driver_fatigue/events"
        payload = json.loads(call.args[1])
        assert payload["event"] == "fatigue_alert"
        assert payload["frame_index"] == 100

    @patch("driver_fatigue.infrastructure.alert_sinks.mqtt.mqtt")
    def test_on_recovery_publishes_recovery_event(self, paho_mock):
        from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink

        client_instance = MagicMock()
        paho_mock.Client.return_value = client_instance

        sink = MqttSink(broker="mqtt.example", topic="driver_fatigue/events")
        sink.on_recovery(frame_index=200)

        assert client_instance.publish.called
        payload = json.loads(client_instance.publish.call_args.args[1])
        assert payload["event"] == "fatigue_recovery"
        assert payload["frame_index"] == 200

    @patch("driver_fatigue.infrastructure.alert_sinks.mqtt.mqtt")
    def test_connect_failure_does_not_raise(self, paho_mock):
        from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink

        client_instance = MagicMock()
        client_instance.connect.side_effect = OSError("broker offline")
        paho_mock.Client.return_value = client_instance

        sink = MqttSink(broker="mqtt.example", topic="t")
        sink.notify(_alert_event())

    @patch("driver_fatigue.infrastructure.alert_sinks.mqtt.mqtt")
    def test_uses_credentials_when_provided(self, paho_mock):
        from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink

        client_instance = MagicMock()
        paho_mock.Client.return_value = client_instance

        MqttSink(broker="x", topic="t", username="u", password="p")
        client_instance.username_pw_set.assert_called_once_with("u", "p")
