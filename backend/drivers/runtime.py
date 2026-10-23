from __future__ import annotations

import json
import math
import random
import sys
import threading
import time
from abc import ABC, abstractmethod
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, BinaryIO
from uuid import uuid4

from polarmarine_gcs.infrastructure.drivers.framing import (
    FrameError,
    IpcFrameDecoder,
    SerialRecordDecoder,
    encode_ipc_message,
    encode_serial_record,
)

FORMAL_TOPICS = {
    "device_info": "/polarmarine/v1/device_info",
    "heartbeat": "/polarmarine/v1/heartbeat",
    "state": "/polarmarine/v1/state",
    "command_request": "/polarmarine/v1/command/request",
    "command_ack": "/polarmarine/v1/command/ack",
    "mission_event": "/polarmarine/v1/mission/event",
}


class DriverHost:
    def __init__(
        self, kind: str, *, stdin: BinaryIO | None = None, stdout: BinaryIO | None = None
    ) -> None:
        self.kind = kind
        self.stdin = stdin or sys.stdin.buffer
        self.stdout = stdout or sys.stdout.buffer
        self.adapter: DriverAdapter
        self._write_lock = threading.Lock()
        self._stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._tick_thread: threading.Thread | None = None

    def run(self) -> int:
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name="driver-heartbeat", daemon=True
        )
        self._heartbeat_thread.start()
        self._tick_thread = threading.Thread(
            target=self._tick_loop, name="driver-adapter-tick", daemon=True
        )
        self._tick_thread.start()
        decoder = IpcFrameDecoder()
        try:
            while not self._stop.is_set():
                read = getattr(self.stdin, "read1", self.stdin.read)
                chunk = read(65_536)
                if not chunk:
                    break
                for message in decoder.feed(chunk):
                    if not self._handle(message):
                        return 0
        except FrameError as exc:
            print(f"invalid core IPC: {exc}", file=sys.stderr, flush=True)
            return 2
        except Exception as exc:
            print(f"driver fatal error: {exc}", file=sys.stderr, flush=True)
            return 1
        finally:
            self._stop.set()
            self.adapter.close()
        return 0

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> None:
        message: dict[str, Any] = {
            "schemaVersion": "1.0",
            "messageId": str(uuid4()),
            "type": event_type,
            "sentAt": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        if correlation_id:
            message["correlationId"] = correlation_id
        frame = encode_ipc_message(message)
        with self._write_lock:
            self.stdout.write(frame)
            self.stdout.flush()

    def stop(self) -> None:
        self._stop.set()

    def _handle(self, message: dict[str, Any]) -> bool:
        message_type = message.get("type")
        payload = message.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        if message_type == "driver.stop":
            self.adapter.close()
            return False
        if message_type == "link.start":
            self.adapter.start_link(payload)
        elif message_type == "link.stop":
            self.adapter.stop_link(str(payload.get("linkId", "")))
        elif message_type == "command.send":
            self.adapter.send_command(str(payload.get("linkId", "")), payload.get("message"))
        elif message_type == "debug.request":
            try:
                response = self.adapter.debug(payload)
            except Exception as exc:
                response = {"ok": False, "error": str(exc)}
            self.emit(
                "debug.response", response, correlation_id=str(message.get("correlationId", ""))
            )
        return True

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(1.0):
            self.emit("driver.heartbeat", {"driver": self.kind})

    def _tick_loop(self) -> None:
        while not self._stop.wait(self.adapter.tick_interval_seconds):
            try:
                self.adapter.tick()
            except Exception as exc:
                print(f"driver tick error: {exc}", file=sys.stderr, flush=True)


class DriverAdapter(ABC):
    tick_interval_seconds = 1.0

    def __init__(self, host: DriverHost) -> None:
        self.host = host

    @abstractmethod
    def start_link(self, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    def stop_link(self, link_id: str) -> None: ...

    @abstractmethod
    def send_command(self, link_id: str, message: object) -> None: ...

    def debug(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "error": "Debug operations are not supported by this driver"}

    def tick(self) -> None:
        return

    @abstractmethod
    def close(self) -> None: ...


class SimulatorAdapter(DriverAdapter):
    tick_interval_seconds = 0.1

    def __init__(self, host: DriverHost) -> None:
        super().__init__(host)
        self.links: dict[str, dict[str, Any]] = {}

    def start_link(self, payload: dict[str, Any]) -> None:
        link_id = str(payload["linkId"])
        device_id = str(payload["expectedDeviceId"])
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        seed = int(config.get("seed", 1))
        randomizer = random.Random(f"{device_id}:{seed}")
        self.links[link_id] = {
            "deviceId": device_id,
            "capabilities": list(payload.get("requestedCapabilities", [])),
            "phase": randomizer.random() * math.tau,
            "lat": float(config.get("latitude", 30.2755)),
            "lon": float(config.get("longitude", 120.1570)),
            "battery": int(config.get("battery", 90)),
            "parameters": dict(config.get("parameterValues", {}))
            if isinstance(config.get("parameterValues"), dict)
            else {},
            "sequence": 0,
            "lastHeartbeatAt": 0.0,
        }
        self.host.emit("link.handshaking", {"linkId": link_id})
        self.host.emit(
            "link.device_info",
            {
                "linkId": link_id,
                "deviceId": device_id,
                "capabilities": self.links[link_id]["capabilities"],
                "adapterVersion": "1.0.0-simulator",
                "simulated": True,
            },
        )

    def stop_link(self, link_id: str) -> None:
        self.links.pop(link_id, None)

    def send_command(self, link_id: str, message: object) -> None:
        link = self.links.get(link_id)
        if link is None or not isinstance(message, dict):
            raise RuntimeError("Simulator link is not active")
        payload = message.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeError("Invalid command envelope")
        command_id = str(payload.get("commandId", message.get("correlationId", "")))
        command_type = str(payload.get("commandType", ""))
        arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}

        def acknowledge() -> None:
            result: dict[str, Any] = {}
            if command_type == "read_parameters":
                defaults = (
                    arguments.get("defaults") if isinstance(arguments.get("defaults"), dict) else {}
                )
                parameters = link["parameters"]
                if isinstance(parameters, dict):
                    for key, value in defaults.items():
                        parameters.setdefault(str(key), value)
                    result = {"values": dict(parameters)}
            elif command_type == "write_parameters":
                values = (
                    arguments.get("values") if isinstance(arguments.get("values"), dict) else {}
                )
                parameters = link["parameters"]
                if isinstance(parameters, dict):
                    parameters.update(values)
                result = {
                    "values": dict(values),
                    "parameterResults": {
                        str(key): {"status": "applied", "value": value}
                        for key, value in values.items()
                    },
                }
            for status, progress in (("accepted", 0.0), ("in_progress", 0.5), ("completed", 1.0)):
                self.host.emit(
                    "command.ack",
                    {
                        "linkId": link_id,
                        "commandId": command_id,
                        "status": status,
                        "progress": progress,
                    },
                )
                time.sleep(0.03)
            self.host.emit(
                "command.ack",
                {
                    "linkId": link_id,
                    "commandId": command_id,
                    "status": "state_confirmed",
                    "stateConfirmed": True,
                    "result": result,
                },
            )

        threading.Thread(target=acknowledge, name=f"sim-ack-{command_id}", daemon=True).start()

    def tick(self) -> None:
        now = datetime.now(UTC)
        monotonic_now = time.monotonic()
        for link_id, link in list(self.links.items()):
            link["sequence"] += 1
            sequence = int(link["sequence"])
            angle = float(link["phase"]) + sequence * 0.03
            if monotonic_now - float(link["lastHeartbeatAt"]) >= 1.0:
                self.host.emit(
                    "link.heartbeat",
                    {"linkId": link_id, "latencyMs": 12, "packetLossPercent": 0.0},
                )
                link["lastHeartbeatAt"] = monotonic_now
            self.host.emit(
                "telemetry.received",
                {
                    "linkId": link_id,
                    "deviceId": link["deviceId"],
                    "sequence": sequence,
                    "simulated": True,
                    "fields": {
                        "position.latitude": {
                            "value": float(link["lat"]) + math.sin(angle) * 0.0001,
                            "unit": "deg",
                            "quality": "simulated",
                            "collectedAt": now.isoformat(),
                        },
                        "position.longitude": {
                            "value": float(link["lon"]) + math.cos(angle) * 0.0001,
                            "unit": "deg",
                            "quality": "simulated",
                            "collectedAt": now.isoformat(),
                        },
                        "home.latitude": {
                            "value": float(link["lat"]),
                            "unit": "deg",
                            "quality": "simulated",
                            "collectedAt": now.isoformat(),
                        },
                        "home.longitude": {
                            "value": float(link["lon"]),
                            "unit": "deg",
                            "quality": "simulated",
                            "collectedAt": now.isoformat(),
                        },
                        "battery.percent": {
                            "value": max(0, int(link["battery"]) - sequence // 600),
                            "unit": "%",
                            "quality": "simulated",
                            "collectedAt": now.isoformat(),
                        },
                        "speed": {
                            "value": 0.3,
                            "unit": "m/s",
                            "quality": "simulated",
                            "collectedAt": now.isoformat(),
                        },
                        "heading": {
                            "value": math.degrees(angle) % 360,
                            "unit": "deg",
                            "quality": "simulated",
                            "collectedAt": now.isoformat(),
                        },
                    },
                },
            )

    def debug(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "driver": "simulator", "activeLinkIds": sorted(self.links)}

    def close(self) -> None:
        self.links.clear()


class SerialAdapter(DriverAdapter):
    def __init__(self, host: DriverHost) -> None:
        super().__init__(host)
        self.links: dict[str, _SerialLink] = {}

    def start_link(self, payload: dict[str, Any]) -> None:
        link_id = str(payload["linkId"])
        self.stop_link(link_id)
        try:
            link = _SerialLink(self.host, payload)
            self.links[link_id] = link
            link.start()
        except Exception as exc:
            self.host.emit(
                "link.failed",
                {"linkId": link_id, "code": _serial_error_code(exc), "message": str(exc)},
            )

    def stop_link(self, link_id: str) -> None:
        link = self.links.pop(link_id, None)
        if link:
            link.close()

    def send_command(self, link_id: str, message: object) -> None:
        link = self.links.get(link_id)
        if link is None or not isinstance(message, dict):
            raise RuntimeError("Serial link is not active")
        link.write(message)

    def debug(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation = payload.get("operation")
        if operation != "list_ports":
            return super().debug(payload)
        from serial.tools import list_ports

        return {
            "ok": True,
            "ports": [
                {
                    "port": item.device,
                    "description": item.description,
                    "manufacturer": item.manufacturer,
                    "hwid": item.hwid,
                }
                for item in list_ports.comports()
            ],
        }

    def close(self) -> None:
        for link_id in list(self.links):
            self.stop_link(link_id)


class _SerialLink:
    def __init__(self, host: DriverHost, payload: dict[str, Any]) -> None:
        import serial

        self.host = host
        self.link_id = str(payload["linkId"])
        self.device_id = str(payload["expectedDeviceId"])
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        self.serial = serial.Serial(
            port=str(config["port"]),
            baudrate=int(config.get("baudRate", 115200)),
            timeout=0.2,
            write_timeout=1.0,
        )
        self.decoder = SerialRecordDecoder()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._read, name=f"serial-{self.link_id}", daemon=True
        )
        self._write_lock = threading.Lock()

    def start(self) -> None:
        self.host.emit("link.handshaking", {"linkId": self.link_id})
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self.serial.is_open:
            self.serial.close()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)

    def write(self, message: dict[str, Any]) -> None:
        frame = encode_serial_record(message)
        with self._write_lock:
            self.serial.write(frame)
            self.serial.flush()

    def _read(self) -> None:
        try:
            while not self._stop.is_set():
                chunk = self.serial.read(4096)
                if not chunk:
                    continue
                for message in self.decoder.feed(chunk):
                    _forward_canonical(self.host, self.link_id, self.device_id, message)
        except Exception as exc:
            if not self._stop.is_set():
                self.host.emit(
                    "link.failed",
                    {"linkId": self.link_id, "code": _serial_error_code(exc), "message": str(exc)},
                )


class RosbridgeAdapter(DriverAdapter):
    def __init__(self, host: DriverHost, ros_version: str) -> None:
        super().__init__(host)
        self.ros_version = ros_version
        self.links: dict[str, _RosbridgeLink] = {}

    def start_link(self, payload: dict[str, Any]) -> None:
        link_id = str(payload["linkId"])
        self.stop_link(link_id)
        link = _RosbridgeLink(self.host, payload, self.ros_version)
        self.links[link_id] = link
        link.start()

    def stop_link(self, link_id: str) -> None:
        link = self.links.pop(link_id, None)
        if link:
            link.close()

    def send_command(self, link_id: str, message: object) -> None:
        link = self.links.get(link_id)
        if link is None or not isinstance(message, dict):
            raise RuntimeError("ROS link is not active")
        link.publish(
            FORMAL_TOPICS["command_request"], {"data": json.dumps(message, separators=(",", ":"))}
        )

    def debug(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("operation") == "discover":
            timeout_seconds = max(0.2, min(3.0, float(payload.get("timeoutSeconds", 1.5))))
            return {
                "ok": True,
                "driver": self.ros_version,
                "candidates": _discover_rosbridge_services(timeout_seconds, self.ros_version),
            }
        link = self.links.get(str(payload.get("linkId", "")))
        if link is None:
            raise RuntimeError("ROS link is not active")
        return link.debug(payload)

    def close(self) -> None:
        for link_id in list(self.links):
            self.stop_link(link_id)


class _RosbridgeLink:
    def __init__(self, host: DriverHost, payload: dict[str, Any], ros_version: str) -> None:
        self.host = host
        self.link_id = str(payload["linkId"])
        self.device_id = str(payload["expectedDeviceId"])
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        scheme = "wss" if config.get("secure") is True else "ws"
        self.url = f"{scheme}://{config['host']}:{int(config.get('port', 9090))}"
        self.ros_version = ros_version
        self.socket: Any = None
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name=f"{ros_version}-{self.link_id}", daemon=True
        )
        self._send_lock = threading.Lock()
        self._debug_topics: set[str] = set()
        self._debug_rate_limit = max(1, min(1_000, int(config.get("debugRateLimit", 50))))
        self._debug_max_message_bytes = max(
            1_024,
            min(1024 * 1024, int(config.get("debugMaxMessageBytes", 256 * 1024))),
        )
        self._debug_window_started = time.monotonic()
        self._debug_message_count = 0
        self._last_drop_notice = 0.0

    def start(self) -> None:
        self.host.emit("link.handshaking", {"linkId": self.link_id})
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self.socket is not None:
            with suppress(Exception):
                self.socket.close()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)

    def publish(self, topic: str, message: dict[str, Any]) -> None:
        self._send({"op": "publish", "topic": topic, "msg": message})

    def debug(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation = str(payload.get("operation", ""))
        if operation == "publish":
            topic = str(payload["topic"])
            self.publish(topic, dict(payload.get("message", {})))
        elif operation == "subscribe":
            topic = str(payload["topic"])
            self._debug_topics.add(topic)
            self._send(
                {
                    "op": "subscribe",
                    "topic": topic,
                    "throttle_rate": int(payload.get("throttleMs", 20)),
                }
            )
        elif operation == "unsubscribe":
            topic = str(payload["topic"])
            self._debug_topics.discard(topic)
            self._send({"op": "unsubscribe", "topic": topic})
        elif operation == "call_service":
            self._send(
                {
                    "op": "call_service",
                    "service": str(payload["service"]),
                    "args": dict(payload.get("arguments", {})),
                    "id": str(uuid4()),
                }
            )
        elif operation in {"nodes", "topics", "services", "params"}:
            self._send(
                {
                    "op": "call_service",
                    "service": f"/rosapi/{operation}",
                    "args": {},
                    "id": str(uuid4()),
                }
            )
        elif operation == "get_param":
            self._send(
                {
                    "op": "call_service",
                    "service": "/rosapi/get_param",
                    "args": {"name": str(payload["parameter"])},
                    "id": str(uuid4()),
                }
            )
        elif operation == "set_param":
            self._send(
                {
                    "op": "call_service",
                    "service": "/rosapi/set_param",
                    "args": {
                        "name": str(payload["parameter"]),
                        "value": json.dumps(payload.get("message")),
                    },
                    "id": str(uuid4()),
                }
            )
        elif operation == "action_goal":
            self.publish(f"{payload['action']!s}/goal", dict(payload.get("message", {})))
        elif operation == "action_cancel":
            self.publish(f"{payload['action']!s}/cancel", dict(payload.get("message", {})))
        else:
            raise ValueError(f"Unsupported ROS debug operation {operation}")
        return {"ok": True, "operation": operation, "linkId": self.link_id}

    def _run(self) -> None:
        try:
            from websockets.sync.client import connect

            with connect(self.url, open_timeout=5, close_timeout=1, max_size=1024 * 1024) as socket:
                self.socket = socket
                self.host.emit("link.debug_ready", {"linkId": self.link_id})
                for topic in (
                    FORMAL_TOPICS["device_info"],
                    FORMAL_TOPICS["heartbeat"],
                    FORMAL_TOPICS["state"],
                    FORMAL_TOPICS["command_ack"],
                    FORMAL_TOPICS["mission_event"],
                ):
                    self._send({"op": "subscribe", "topic": topic})
                while not self._stop.is_set():
                    try:
                        raw = socket.recv(timeout=1.0)
                    except TimeoutError:
                        continue
                    if raw is None:
                        continue
                    ros_message = json.loads(raw)
                    topic = ros_message.get("topic")
                    if topic in self._debug_topics:
                        if not self._allow_debug_message(ros_message):
                            self._emit_debug_drop(str(topic))
                            continue
                        self.host.emit(
                            "debug.ros_message",
                            {
                                "linkId": self.link_id,
                                "topic": topic,
                                "message": ros_message.get("msg"),
                            },
                        )
                        continue
                    if ros_message.get("op") == "service_response":
                        self.host.emit(
                            "debug.ros_response",
                            {"linkId": self.link_id, "response": ros_message},
                        )
                        continue
                    canonical = _extract_ros_canonical(ros_message.get("msg"))
                    if canonical:
                        _forward_canonical(self.host, self.link_id, self.device_id, canonical)
        except Exception as exc:
            if not self._stop.is_set():
                self.host.emit(
                    "link.failed",
                    {"linkId": self.link_id, "code": "ROSBRIDGE_FAILED", "message": str(exc)},
                )
        finally:
            self.socket = None

    def _allow_debug_message(self, message: dict[str, Any]) -> bool:
        now = time.monotonic()
        if now - self._debug_window_started >= 1.0:
            self._debug_window_started = now
            self._debug_message_count = 0
        encoded_size = len(
            json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        if encoded_size > self._debug_max_message_bytes:
            return False
        if self._debug_message_count >= self._debug_rate_limit:
            return False
        self._debug_message_count += 1
        return True

    def _emit_debug_drop(self, topic: str) -> None:
        now = time.monotonic()
        if now - self._last_drop_notice < 1.0:
            return
        self._last_drop_notice = now
        self.host.emit(
            "debug.ros_dropped",
            {
                "linkId": self.link_id,
                "topic": topic,
                "reason": "RATE_OR_SIZE_LIMIT",
                "rateLimit": self._debug_rate_limit,
                "maxMessageBytes": self._debug_max_message_bytes,
            },
        )

    def _send(self, message: dict[str, Any]) -> None:
        if self.socket is None:
            raise RuntimeError("rosbridge is not connected")
        with self._send_lock:
            self.socket.send(json.dumps(message, ensure_ascii=False, separators=(",", ":")))


def create_adapter(kind: str, host: DriverHost) -> DriverAdapter:
    if kind == "simulator":
        return SimulatorAdapter(host)
    if kind == "serial_json":
        return SerialAdapter(host)
    if kind in {"ros1", "ros2"}:
        return RosbridgeAdapter(host, kind)
    raise ValueError(f"Unknown driver kind {kind}")


def _extract_ros_canonical(message: object) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return None
    value: object = message.get("data", message)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _forward_canonical(
    host: DriverHost,
    link_id: str,
    expected_device_id: str,
    message: dict[str, Any],
) -> None:
    validation_error = _canonical_validation_error(message)
    if validation_error:
        host.emit(
            "link.degraded",
            {
                "linkId": link_id,
                "code": "PROTOCOL_MESSAGE_INVALID",
                "message": validation_error,
            },
        )
        return
    message_type = message.get("type")
    device_id = message.get("deviceId")
    payload = message.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    if message_type == "device_info":
        host.emit(
            "link.device_info",
            {
                "linkId": link_id,
                "deviceId": device_id,
                "capabilities": payload.get("capabilities", []),
                "adapterVersion": payload.get("adapterVersion"),
            },
        )
    elif message_type == "heartbeat":
        host.emit(
            "link.heartbeat",
            {
                "linkId": link_id,
                "deviceId": device_id,
                "latencyMs": payload.get("latencyMs"),
                "packetLossPercent": payload.get("packetLossPercent"),
            },
        )
    elif message_type == "state":
        host.emit(
            "telemetry.received",
            {
                "linkId": link_id,
                "deviceId": device_id or expected_device_id,
                "sequence": message.get("sequence"),
                "fields": payload.get("fields", {}),
            },
        )
    elif message_type == "command.ack":
        host.emit(
            "command.ack",
            {
                "linkId": link_id,
                "commandId": message.get("correlationId") or payload.get("commandId"),
                "status": payload.get("status"),
                "progress": payload.get("progress"),
                "reasonCode": payload.get("reasonCode"),
                "reasonMessage": payload.get("reasonMessage"),
                "stateConfirmed": payload.get("stateConfirmed"),
                "result": payload.get("result"),
            },
        )


def _canonical_validation_error(message: dict[str, Any]) -> str | None:
    if message.get("schemaVersion") != "1.0":
        return "Unsupported or missing schemaVersion"
    if not isinstance(message.get("deviceId"), str) or not message["deviceId"]:
        return "deviceId must be a non-empty string"
    if not isinstance(message.get("messageId"), str) or not message["messageId"]:
        return "messageId must be a non-empty string"
    sequence = message.get("sequence")
    if (
        isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or not 0 <= sequence <= 0xFFFFFFFF
    ):
        return "sequence must be an unsigned 32-bit integer"
    sent_at = message.get("sentAt")
    if not isinstance(sent_at, str):
        return "sentAt must be an ISO-8601 timestamp"
    try:
        parsed = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
    except ValueError:
        return "sentAt must be an ISO-8601 timestamp"
    if parsed.tzinfo is None:
        return "sentAt must include a timezone"
    if not isinstance(message.get("type"), str) or not message["type"]:
        return "type must be a non-empty string"
    if "correlationId" not in message:
        return "correlationId must be present"
    correlation_id = message.get("correlationId")
    if correlation_id is not None and not isinstance(correlation_id, str):
        return "correlationId must be a string or null"
    if not isinstance(message.get("payload"), dict):
        return "payload must be an object"
    return None


def _discover_rosbridge_services(timeout_seconds: float, ros_version: str) -> list[dict[str, Any]]:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

    candidates: dict[tuple[str, int], dict[str, Any]] = {}
    zeroconf = Zeroconf()

    class Listener(ServiceListener):
        def add_service(self, discovery: Zeroconf, service_type: str, name: str) -> None:
            info = discovery.get_service_info(service_type, name, timeout=500)
            if info is None:
                return
            properties = {
                key.decode("utf-8", errors="replace"): value.decode("utf-8", errors="replace")
                for key, value in info.properties.items()
            }
            addresses = info.parsed_scoped_addresses()
            host = addresses[0] if addresses else info.server.rstrip(".")
            device_id = properties.get("deviceId")
            schema_version = properties.get("schemaVersion")
            advertised_ros = properties.get("rosVersion")
            candidates[(host, info.port)] = {
                "serviceName": name,
                "host": host,
                "port": info.port,
                "addresses": addresses,
                "deviceId": device_id,
                "schemaVersion": schema_version,
                "rosVersion": advertised_ros,
                "identityVerified": bool(
                    device_id
                    and schema_version == "1.0"
                    and advertised_ros in {None, ros_version}
                    and service_type == "_polarmarine._tcp.local."
                ),
            }

        def update_service(self, discovery: Zeroconf, service_type: str, name: str) -> None:
            self.add_service(discovery, service_type, name)

        def remove_service(self, discovery: Zeroconf, service_type: str, name: str) -> None:
            return

    browsers = [
        ServiceBrowser(zeroconf, service_type, Listener())
        for service_type in ("_polarmarine._tcp.local.", "_rosbridge._tcp.local.")
    ]
    try:
        time.sleep(timeout_seconds)
    finally:
        for browser in browsers:
            browser.cancel()
        zeroconf.close()
    return sorted(
        candidates.values(), key=lambda item: (not item["identityVerified"], item["host"])
    )


def _serial_error_code(exc: Exception) -> str:
    text = str(exc).lower()
    if "access" in text or "permission" in text or "denied" in text:
        return "SERIAL_PORT_BUSY"
    if "not found" in text or "cannot find" in text or "no such file" in text:
        return "SERIAL_PORT_NOT_FOUND"
    return "SERIAL_IO_ERROR"
