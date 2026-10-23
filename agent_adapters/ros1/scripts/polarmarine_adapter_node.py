#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import rospy
from std_msgs.msg import String

TOPIC_PREFIX = "/polarmarine/v1"


class PolarMarineRos1Adapter:
    def __init__(self) -> None:
        self.device_id = str(rospy.get_param("~device_id"))
        self.capabilities = [str(item) for item in rospy.get_param("~capabilities", [])]
        self.sequence = 0
        self.seen_commands: OrderedDict[str, None] = OrderedDict()
        self.mdns = _start_mdns(
            self.device_id,
            "ros1",
            int(rospy.get_param("~rosbridge_port", 9090)),
            bool(rospy.get_param("~advertise_mdns", True)),
        )
        rospy.on_shutdown(self._shutdown)
        self.device_info_pub = rospy.Publisher(
            f"{TOPIC_PREFIX}/device_info", String, queue_size=1, latch=True
        )
        self.heartbeat_pub = rospy.Publisher(f"{TOPIC_PREFIX}/heartbeat", String, queue_size=10)
        self.state_pub = rospy.Publisher(f"{TOPIC_PREFIX}/state", String, queue_size=20)
        self.ack_pub = rospy.Publisher(f"{TOPIC_PREFIX}/command/ack", String, queue_size=20)
        self.mission_pub = rospy.Publisher(f"{TOPIC_PREFIX}/mission/event", String, queue_size=20)
        self.local_command_pub = rospy.Publisher(
            rospy.get_param("~command_output_topic", "/polarmarine/local/command"),
            String,
            queue_size=20,
        )
        rospy.Subscriber(f"{TOPIC_PREFIX}/command/request", String, self._on_command)
        rospy.Subscriber(
            rospy.get_param("~state_input_topic", "/polarmarine/local/state"),
            String,
            self._on_state,
        )
        rospy.Subscriber(
            rospy.get_param("~command_ack_input_topic", "/polarmarine/local/command_ack"),
            String,
            self._on_ack,
        )
        rospy.Subscriber(
            rospy.get_param("~mission_event_input_topic", "/polarmarine/local/mission_event"),
            String,
            self._on_mission_event,
        )
        rospy.Timer(rospy.Duration(1.0), self._heartbeat)
        self._publish(
            self.device_info_pub,
            "device_info",
            {
                "adapterVersion": "1.0.0",
                "rosVersion": "ros1",
                "capabilities": self.capabilities,
            },
        )

    def _envelope(
        self,
        message_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        return {
            "schemaVersion": "1.0",
            "deviceId": self.device_id,
            "messageId": str(uuid4()),
            "sequence": self.sequence,
            "sentAt": datetime.now(UTC).isoformat(),
            "type": message_type,
            "correlationId": correlation_id,
            "payload": payload,
        }

    def _publish(
        self,
        publisher: rospy.Publisher,
        message_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        publisher.publish(
            String(
                data=json.dumps(
                    self._envelope(message_type, payload, correlation_id),
                    separators=(",", ":"),
                )
            )
        )

    def _heartbeat(self, _event: rospy.timer.TimerEvent) -> None:
        self._publish(self.heartbeat_pub, "heartbeat", {"adapterReady": True})

    def _shutdown(self) -> None:
        if self.mdns is not None:
            self.mdns.close()

    def _on_command(self, message: String) -> None:
        try:
            envelope = json.loads(message.data)
            if (
                envelope.get("deviceId") != self.device_id
                or envelope.get("type") != "command.request"
            ):
                return
            command_id = str(envelope.get("correlationId") or envelope["payload"]["commandId"])
            if command_id in self.seen_commands:
                self._publish(
                    self.ack_pub,
                    "command.ack",
                    {"commandId": command_id, "status": "accepted", "duplicate": True},
                    command_id,
                )
                return
            self.seen_commands[command_id] = None
            while len(self.seen_commands) > 2048:
                self.seen_commands.popitem(last=False)
            self.local_command_pub.publish(message)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            rospy.logwarn("Rejected malformed PolarMarine command: %s", exc)

    def _on_state(self, message: String) -> None:
        self._forward_local(self.state_pub, "state", message)

    def _on_ack(self, message: String) -> None:
        self._forward_local(self.ack_pub, "command.ack", message, use_command_id=True)

    def _on_mission_event(self, message: String) -> None:
        self._forward_local(self.mission_pub, "mission.event", message)

    def _forward_local(
        self,
        publisher: rospy.Publisher,
        message_type: str,
        message: String,
        *,
        use_command_id: bool = False,
    ) -> None:
        try:
            payload = json.loads(message.data)
            if not isinstance(payload, dict):
                raise TypeError("payload is not an object")
            correlation_id = str(payload.get("commandId")) if use_command_id else None
            self._publish(publisher, message_type, payload, correlation_id)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            rospy.logwarn("Rejected malformed local %s payload: %s", message_type, exc)


def main() -> None:
    rospy.init_node("polarmarine_adapter")
    PolarMarineRos1Adapter()
    rospy.spin()


class _MdnsAdvertisement:
    def __init__(self, zeroconf: Any, info: Any) -> None:
        self.zeroconf = zeroconf
        self.info = info

    def close(self) -> None:
        self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()


def _start_mdns(
    device_id: str, ros_version: str, port: int, enabled: bool
) -> _MdnsAdvertisement | None:
    if not enabled:
        return None
    try:
        from zeroconf import ServiceInfo, Zeroconf

        hostname = socket.gethostname()
        addresses = [
            socket.inet_aton(address)
            for address in socket.gethostbyname_ex(hostname)[2]
            if not address.startswith("127.")
        ]
        if not addresses:
            raise RuntimeError("no non-loopback IPv4 address")
        service_type = "_polarmarine._tcp.local."
        info = ServiceInfo(
            service_type,
            f"{device_id}.{service_type}",
            addresses=addresses,
            port=port,
            properties={
                "deviceId": device_id,
                "schemaVersion": "1.0",
                "rosVersion": ros_version,
            },
            server=f"{hostname}.local.",
        )
        zeroconf = Zeroconf()
        zeroconf.register_service(info)
        return _MdnsAdvertisement(zeroconf, info)
    except Exception as exc:
        rospy.logwarn("PolarMarine mDNS advertisement unavailable: %s", exc)
        return None


if __name__ == "__main__":
    main()
