from __future__ import annotations

import json
import socket
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

TOPIC_PREFIX = "/polarmarine/v1"


class PolarMarineRos2Adapter(Node):
    def __init__(self) -> None:
        super().__init__("polarmarine_adapter")
        self.declare_parameter("device_id", "")
        self.declare_parameter("capabilities", [])
        self.declare_parameter("state_input_topic", "/polarmarine/local/state")
        self.declare_parameter("command_output_topic", "/polarmarine/local/command")
        self.declare_parameter("command_ack_input_topic", "/polarmarine/local/command_ack")
        self.declare_parameter("mission_event_input_topic", "/polarmarine/local/mission_event")
        self.declare_parameter("rosbridge_port", 9090)
        self.declare_parameter("advertise_mdns", True)
        self.device_id = str(self.get_parameter("device_id").value)
        if not self.device_id:
            raise ValueError("device_id parameter is required")
        self.capabilities = [str(item) for item in self.get_parameter("capabilities").value]
        self.sequence = 0
        self.seen_commands: OrderedDict[str, None] = OrderedDict()
        self.mdns = _start_mdns(
            self.device_id,
            "ros2",
            int(self.get_parameter("rosbridge_port").value),
            bool(self.get_parameter("advertise_mdns").value),
            self,
        )
        device_info_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.device_info_pub = self.create_publisher(
            String, f"{TOPIC_PREFIX}/device_info", device_info_qos
        )
        self.heartbeat_pub = self.create_publisher(String, f"{TOPIC_PREFIX}/heartbeat", 10)
        self.state_pub = self.create_publisher(String, f"{TOPIC_PREFIX}/state", 20)
        self.ack_pub = self.create_publisher(String, f"{TOPIC_PREFIX}/command/ack", 20)
        self.mission_pub = self.create_publisher(String, f"{TOPIC_PREFIX}/mission/event", 20)
        self.local_command_pub = self.create_publisher(
            String, str(self.get_parameter("command_output_topic").value), 20
        )
        self.create_subscription(String, f"{TOPIC_PREFIX}/command/request", self._on_command, 20)
        self.create_subscription(
            String,
            str(self.get_parameter("state_input_topic").value),
            self._on_state,
            20,
        )
        self.create_subscription(
            String,
            str(self.get_parameter("command_ack_input_topic").value),
            self._on_ack,
            20,
        )
        self.create_subscription(
            String,
            str(self.get_parameter("mission_event_input_topic").value),
            self._on_mission_event,
            20,
        )
        self.create_timer(1.0, self._heartbeat)
        self._publish(
            self.device_info_pub,
            "device_info",
            {
                "adapterVersion": "1.0.0",
                "rosVersion": "ros2",
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
        publisher: Any,
        message_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        message = String()
        message.data = json.dumps(
            self._envelope(message_type, payload, correlation_id), separators=(",", ":")
        )
        publisher.publish(message)

    def _heartbeat(self) -> None:
        self._publish(self.heartbeat_pub, "heartbeat", {"adapterReady": True})

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
            self.get_logger().warning(f"Rejected malformed PolarMarine command: {exc}")

    def _on_state(self, message: String) -> None:
        self._forward_local(self.state_pub, "state", message)

    def _on_ack(self, message: String) -> None:
        self._forward_local(self.ack_pub, "command.ack", message, use_command_id=True)

    def _on_mission_event(self, message: String) -> None:
        self._forward_local(self.mission_pub, "mission.event", message)

    def _forward_local(
        self,
        publisher: Any,
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
            self.get_logger().warning(f"Rejected malformed local {message_type} payload: {exc}")

    def destroy_node(self) -> bool:
        if self.mdns is not None:
            self.mdns.close()
            self.mdns = None
        return super().destroy_node()


class _MdnsAdvertisement:
    def __init__(self, zeroconf: Any, info: Any) -> None:
        self.zeroconf = zeroconf
        self.info = info

    def close(self) -> None:
        self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()


def _start_mdns(
    device_id: str,
    ros_version: str,
    port: int,
    enabled: bool,
    node: Node,
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
        node.get_logger().warning(f"PolarMarine mDNS advertisement unavailable: {exc}")
        return None


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = PolarMarineRos2Adapter()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
