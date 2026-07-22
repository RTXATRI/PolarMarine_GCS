from __future__ import annotations

import asyncio
from contextlib import suppress
import threading
from typing import Any, Callable, Protocol

try:
    import roslibpy
except ImportError:  # pragma: no cover - production dependency is declared
    roslibpy = None  # type: ignore[assignment]


RosMessageCallback = Callable[[dict[str, Any]], None]
RosCloseCallback = Callable[[str], None]


class RosbridgeTransport(Protocol):
    @property
    def connected(self) -> bool: ...

    async def open(self, on_message: RosMessageCallback, on_close: RosCloseCallback) -> None: ...

    async def close(self) -> None: ...

    async def publish_bool(self, topic_name: str, value: bool) -> None: ...


RosSessionFactory = Callable[[str, int, str, float], RosbridgeTransport]


class RoslibpySession:
    """Thin asynchronous owner for one robot's ROSBridge connection."""

    def __init__(self, host: str, port: int, topic_name: str, connect_timeout_sec: float) -> None:
        self.host = host
        self.port = port
        self.topic_name = topic_name
        self.connect_timeout_sec = connect_timeout_sec
        self.client: Any | None = None
        self.topic: Any | None = None
        self.publishers: dict[str, Any] = {}
        self._on_message: RosMessageCallback | None = None
        self._on_close: RosCloseCallback | None = None
        self._closing = False
        self._close_notified = False
        self._lock = threading.RLock()

    @property
    def connected(self) -> bool:
        with self._lock:
            return bool(self.client and getattr(self.client, "is_connected", False) and not self._closing)

    async def open(self, on_message: RosMessageCallback, on_close: RosCloseCallback) -> None:
        self._on_message = on_message
        self._on_close = on_close
        await asyncio.to_thread(self._open_sync)

    def _open_sync(self) -> None:
        if roslibpy is None:
            raise RuntimeError("roslibpy 未安装，无法建立 ROSBridge 连接")

        with self._lock:
            if self.client is not None:
                raise RuntimeError("ROSBridge 会话已打开")
            self._closing = False
            self._close_notified = False
            client = roslibpy.Ros(host=self.host, port=self.port)
            # Disable roslibpy/Twisted's unbounded reconnect loop. The
            # ConnectionManager owns the explicit 1/2/4 second retry policy.
            client.factory.maxRetries = 0
            self.client = client
            client.on("close", self._handle_close)

        try:
            client.run(timeout=self.connect_timeout_sec)
            if not client.is_connected:
                raise TimeoutError(f"连接 ROSBridge 超时（{self.connect_timeout_sec:g}s）")
            topic = roslibpy.Topic(
                client,
                self.topic_name,
                "std_msgs/String",
                reconnect_on_close=False,
            )
            with self._lock:
                if self._closing:
                    raise RuntimeError("ROSBridge 会话已取消")
                self.topic = topic
            topic.subscribe(self._handle_message)
        except Exception:
            self._close_sync()
            raise

    async def close(self) -> None:
        await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        with self._lock:
            self._closing = True
            topic = self.topic
            publishers = list(self.publishers.values())
            client = self.client
            self.topic = None
            self.publishers = {}
            self.client = None
        if topic is not None:
            with suppress(Exception):
                topic.unsubscribe()
        for publisher in publishers:
            with suppress(Exception):
                publisher.unadvertise()
        if client is not None:
            if bool(getattr(client, "is_connected", False)):
                with suppress(Exception):
                    # roslibpy shares a process-level Twisted reactor.
                    # Terminating it from one device would break all others.
                    client.close(timeout=1)
            else:
                # A timed-out TCP attempt has no websocket protocol for
                # Ros.close(). Stop that factory and connector on the reactor
                # thread so it cannot connect after our bounded attempt ended.
                with suppress(Exception):
                    factory = client.factory
                    connector = factory.connector

                    def stop_pending_connection() -> None:
                        factory.stopTrying()
                        if connector is not None:
                            connector.disconnect()

                    factory.manager.call_later(0, stop_pending_connection)

    async def publish_bool(self, topic_name: str, value: bool) -> None:
        await asyncio.to_thread(self._publish_bool_sync, topic_name, value)

    def _publish_bool_sync(self, topic_name: str, value: bool) -> None:
        if roslibpy is None:
            raise RuntimeError('roslibpy 未安装，无法发布继电器命令')
        with self._lock:
            client = self.client
            if self._closing or client is None or not getattr(client, 'is_connected', False):
                raise RuntimeError('ROSBridge 会话未连接')
            publisher = self.publishers.get(topic_name)
            if publisher is None:
                publisher = roslibpy.Topic(
                    client,
                    topic_name,
                    'std_msgs/Bool',
                    reconnect_on_close=False,
                )
                self.publishers[topic_name] = publisher
            publisher.publish(roslibpy.Message({'data': bool(value)}))

    def _handle_message(self, message: dict[str, Any]) -> None:
        with self._lock:
            callback = None if self._closing else self._on_message
        if callback and isinstance(message, dict):
            callback(message)

    def _handle_close(self, *args: object) -> None:
        with self._lock:
            if self._closing or self._close_notified:
                return
            self._close_notified = True
            callback = self._on_close
        if callback:
            reason = str(args[0]) if args else "ROSBridge 连接已关闭"
            callback(reason)


def create_rosbridge_session(host: str, port: int, topic_name: str, connect_timeout_sec: float) -> RosbridgeTransport:
    return RoslibpySession(host, port, topic_name, connect_timeout_sec)
