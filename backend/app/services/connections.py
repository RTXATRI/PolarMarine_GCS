from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
import socket
import time
from typing import Any, Callable

try:
    import psutil
except ImportError:  # pragma: no cover - dependency is declared for production
    psutil = None  # type: ignore[assignment]

try:
    import serial as serial_module
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - dependency is declared for production
    serial_module = None  # type: ignore[assignment]
    list_ports = None  # type: ignore[assignment]

from app.models.schemas import (
    ConnectionProfile,
    NetworkCandidate,
    NetworkConnectionProfile,
    Robot,
    SerialConnectionProfile,
    SerialPortInfo,
)
from app.services.message_mapper import ParsedRosState, RosMessageError, parse_ros_state_message
from app.services.profile_store import DeviceProfileStore
from app.services import rosbridge as rosbridge_module
from app.services.state import StateService, state_service
from app.ws.telemetry import telemetry_manager


class ConnectionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409, robot: Robot | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.robot = robot

    def detail(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "robot": self.robot.model_dump(mode="json") if self.robot else None,
        }


class SerialSession:
    def __init__(self, port: str, handle: Any) -> None:
        self.port = port
        self.handle = handle


@dataclass
class NetworkSession:
    profile: NetworkConnectionProfile
    transport: rosbridge_module.RosbridgeTransport
    generation: int
    first_message: asyncio.Future[tuple[ParsedRosState, float, float]]
    relay_command_lock: asyncio.Lock
    ready: bool = False
    closing: bool = False
    last_valid_monotonic: float | None = None
    invalid_message_logged: bool = False
    relay_confirmation: tuple[bool, asyncio.Future[None]] | None = None


class ConnectionManager:
    def __init__(
        self,
        profile_path: Path,
        monitor_interval_sec: float = 1.0,
        state: StateService = state_service,
        serial_factory: Callable[..., Any] | None = None,
        ros_session_factory: rosbridge_module.RosSessionFactory | None = None,
        ros_topic_state: str = "/gcs/robot_state",
        ros_connect_timeout_sec: float = 5.0,
        ros_first_message_timeout_sec: float = 3.0,
        ros_stale_timeout_sec: float = 3.0,
        ros_watchdog_interval_sec: float = 0.5,
        ros_reconnect_delays_sec: tuple[float, ...] = (1.0, 2.0, 4.0),
        dock_test_ip: str = "192.0.2.42",
        usv_relay_command_topic: str = '/usv_std/relay/set_enabled',
        usv_relay_confirmation_timeout_sec: float = 2.0,
    ) -> None:
        self.state = state
        self.profile_store = DeviceProfileStore(profile_path)
        self.monitor_interval_sec = monitor_interval_sec
        self.ros_topic_state = ros_topic_state
        self.ros_connect_timeout_sec = ros_connect_timeout_sec
        self.ros_first_message_timeout_sec = ros_first_message_timeout_sec
        self.ros_stale_timeout_sec = ros_stale_timeout_sec
        self.ros_watchdog_interval_sec = ros_watchdog_interval_sec
        self.ros_reconnect_delays_sec = ros_reconnect_delays_sec
        self.dock_test_ip = str(IPv4Address(dock_test_ip))
        self.usv_relay_command_topic = usv_relay_command_topic
        self.usv_relay_confirmation_timeout_sec = usv_relay_confirmation_timeout_sec
        self._serial_factory = serial_factory or (serial_module.Serial if serial_module else None)
        self._ros_session_factory = ros_session_factory or rosbridge_module.create_rosbridge_session
        self._serial_sessions: dict[str, SerialSession] = {}
        self._port_owners: dict[str, str] = {}
        self._network_sessions: dict[str, NetworkSession] = {}
        self._endpoint_owners: dict[str, str] = {}
        self._generations: dict[str, int] = {}
        self._reconnect_tasks: dict[str, asyncio.Task[None]] = {}
        self._robot_locks: dict[str, asyncio.Lock] = {}
        self._serial_monitor_task: asyncio.Task[None] | None = None
        self._network_monitor_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopping = False

    @property
    def connected_ros_count(self) -> int:
        return sum(1 for session in self._network_sessions.values() if session.ready and session.transport.connected)

    def _robot_lock(self, robot_id: str) -> asyncio.Lock:
        lock = self._robot_locks.get(robot_id)
        if lock is None:
            lock = asyncio.Lock()
            self._robot_locks[robot_id] = lock
        return lock

    async def start(self) -> None:
        self.state.reset(self.profile_store.load())
        self._loop = asyncio.get_running_loop()
        self._stopping = False
        if self._serial_monitor_task is None or self._serial_monitor_task.done():
            self._serial_monitor_task = asyncio.create_task(self._monitor_serial_connections())
        if self._network_monitor_task is None or self._network_monitor_task.done():
            self._network_monitor_task = asyncio.create_task(self._monitor_network_connections())

    async def stop(self) -> None:
        self._stopping = True
        monitor_tasks = [task for task in (self._serial_monitor_task, self._network_monitor_task) if task]
        self._serial_monitor_task = None
        self._network_monitor_task = None
        for task in monitor_tasks:
            task.cancel()
        if monitor_tasks:
            await asyncio.gather(*monitor_tasks, return_exceptions=True)

        reconnect_tasks = list(self._reconnect_tasks.values())
        self._reconnect_tasks.clear()
        for task in reconnect_tasks:
            task.cancel()
        if reconnect_tasks:
            await asyncio.gather(*reconnect_tasks, return_exceptions=True)

        serial_sessions = list(self._serial_sessions.values())
        self._serial_sessions.clear()
        self._port_owners.clear()
        for session in serial_sessions:
            await asyncio.to_thread(self._close_serial_handle, session.handle)

        network_sessions = list(self._network_sessions.items())
        self._network_sessions.clear()
        self._endpoint_owners.clear()
        for robot_id, session in network_sessions:
            session.closing = True
            self._reject_relay_confirmation(
                robot_id,
                session,
                'DEVICE_NOT_CONNECTED',
                '应用正在关闭，CL-USV 连接已释放',
            )
            with suppress(Exception):
                await session.transport.close()
        self._loop = None

    def list_serial_ports_sync(self) -> list[SerialPortInfo]:
        if list_ports is None:
            return []
        ports: list[SerialPortInfo] = []
        try:
            discovered_ports = list(list_ports.comports())
        except Exception as exc:
            raise ConnectionServiceError(
                "SERIAL_ENUMERATION_FAILED",
                f"串口设备枚举失败：{exc}",
                status_code=503,
            ) from exc
        for item in discovered_ports:
            port = str(getattr(item, "device", "") or "").strip()
            if not port:
                continue
            ports.append(
                SerialPortInfo(
                    port=port,
                    description=str(getattr(item, "description", "") or port),
                    manufacturer=getattr(item, "manufacturer", None) or None,
                    hwid=getattr(item, "hwid", None) or None,
                )
            )
        return sorted(ports, key=lambda item: item.port.casefold())

    async def list_serial_ports(self) -> list[SerialPortInfo]:
        return await asyncio.to_thread(self.list_serial_ports_sync)

    async def discover_network_candidates(self, port: int) -> list[NetworkCandidate]:
        addresses = await asyncio.to_thread(self._network_scan_addresses)
        if not addresses:
            return []

        semaphore = asyncio.Semaphore(64)
        tasks = [asyncio.create_task(self._probe_network_host(str(address), port, semaphore)) for address in addresses]
        done, pending = await asyncio.wait(tasks, timeout=5.0)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        found: list[NetworkCandidate] = []
        for task in done:
            if task.cancelled() or task.exception():
                continue
            candidate = task.result()
            if candidate:
                found.append(candidate)
        return sorted(found, key=lambda item: int(IPv4Address(item.host)))

    def _network_scan_addresses(self) -> list[IPv4Address]:
        if psutil is None:
            return []
        try:
            interface_addresses = psutil.net_if_addrs()
            interface_stats = psutil.net_if_stats()
        except (OSError, RuntimeError):
            return []

        addresses: set[IPv4Address] = set()
        for interface_name, records in interface_addresses.items():
            stats = interface_stats.get(interface_name)
            if stats is not None and not stats.isup:
                continue
            for record in records:
                if record.family != socket.AF_INET:
                    continue
                try:
                    address = IPv4Address(record.address)
                    if not address.is_private or address.is_loopback or address.is_link_local:
                        continue
                    network = IPv4Network(f"{record.address}/{record.netmask or '255.255.255.0'}", strict=False)
                    if network.prefixlen < 24:
                        network = IPv4Network(f"{record.address}/24", strict=False)
                    addresses.update(network.hosts())
                    break
                except ValueError:
                    continue
        return sorted(addresses, key=int)

    async def _probe_network_host(self, host: str, port: int, semaphore: asyncio.Semaphore) -> NetworkCandidate | None:
        async with semaphore:
            started = time.perf_counter()
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=0.25)
            except (TimeoutError, OSError):
                return None
            latency_ms = max(0, round((time.perf_counter() - started) * 1000))
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()

            hostname: str | None = None
            try:
                hostname_result = await asyncio.wait_for(asyncio.to_thread(socket.gethostbyaddr, host), timeout=0.2)
                hostname = hostname_result[0]
            except (TimeoutError, OSError):
                pass
            return NetworkCandidate(host=host, hostname=hostname, port=port, latencyMs=latency_ms)

    async def connect(self, robot_id: str, profile: ConnectionProfile) -> Robot:
        async with self._robot_lock(robot_id):
            robot = self.state.get_robot(robot_id)
            if not robot:
                raise ConnectionServiceError("ROBOT_NOT_FOUND", "设备不存在", status_code=404)
            if robot.connection.state in ("connecting", "connected"):
                raise ConnectionServiceError("ALREADY_CONNECTED", "设备已连接或正在连接", robot=robot)

            await self._cancel_reconnect(robot_id)
            self.state.set_connection_profile(robot_id, profile)
            self.profile_store.save(self.state.saved_profiles())
            self.state.mark_connecting(robot_id, profile)
            endpoint = self.state._profile_endpoint(profile)
            self.state.append_log("通信", robot_id, f"正在通过{self._method_label(profile)}连接 {endpoint}")
            await self.broadcast_snapshots()

            claimed_endpoint = False
            try:
                if profile.method == "serial":
                    handle = await asyncio.to_thread(self._open_serial_sync, robot_id, profile)
                    normalized_port = self._normalize_port(profile.port)
                    self._serial_sessions[robot_id] = SerialSession(profile.port, handle)
                    self._port_owners[normalized_port] = robot_id
                    connected = self.state.mark_connected(robot_id, profile, "none", "none")
                else:
                    self._claim_network_endpoint(robot_id, profile)
                    claimed_endpoint = True
                    if robot.id == "SmartDock-1" and str(profile.host) == self.dock_test_ip:
                        connected = self.state.mark_connected(robot_id, profile, "virtual", "virtual")
                    else:
                        connected = await self._open_live_session(robot_id, profile)
            except ConnectionServiceError as exc:
                await self._discard_network_session(robot_id)
                if claimed_endpoint:
                    self._release_network_endpoint(robot_id, profile)
                failed = self.state.mark_connection_error(robot_id, exc.code, exc.message, preserve_last_comm=False)
                self.state.append_log("通信", robot_id, f"连接失败：{exc.message}")
                await self.broadcast_snapshots()
                exc.robot = failed
                raise

            if not connected:
                raise ConnectionServiceError("ROBOT_NOT_FOUND", "设备不存在", status_code=404)
            label = "ROSBridge 实时连接" if connected.connection.dataMode == "live" else f"{self._method_label(profile)}连接"
            self.state.append_log("通信", robot_id, f"{label}已建立")
            await self.broadcast_snapshots()
            return connected

    async def disconnect(self, robot_id: str) -> Robot:
        async with self._robot_lock(robot_id):
            robot = self.state.get_robot(robot_id)
            if not robot:
                raise ConnectionServiceError("ROBOT_NOT_FOUND", "设备不存在", status_code=404)
            if robot.connection.state == "disconnected":
                raise ConnectionServiceError("DEVICE_NOT_CONNECTED", "设备尚未连接", robot=robot)

            await self._cancel_reconnect(robot_id)
            session = self._serial_sessions.pop(robot_id, None)
            if session:
                self._port_owners.pop(self._normalize_port(session.port), None)
                await asyncio.to_thread(self._close_serial_handle, session.handle)

            network_profile = robot.connectionProfile if robot.connectionProfile and robot.connectionProfile.method == "network" else None
            self._next_generation(robot_id)
            await self._discard_network_session(robot_id)
            if network_profile:
                self._release_network_endpoint(robot_id, network_profile)

            disconnected = self.state.mark_disconnected(robot_id)
            self.state.append_log("通信", robot_id, "设备已主动断开")
            await self.broadcast_snapshots()
            if not disconnected:
                raise ConnectionServiceError("ROBOT_NOT_FOUND", "设备不存在", status_code=404)
            return disconnected

    async def set_electromagnetic_fix(self, robot_id: str, enabled: bool) -> Robot:
        robot = self.state.get_robot(robot_id)
        if not robot:
            raise ConnectionServiceError('ROBOT_NOT_FOUND', '设备不存在', status_code=404)
        if robot_id != 'CL-USV':
            raise ConnectionServiceError(
                'ACTION_NOT_SUPPORTED',
                '当前设备不支持电磁固定',
                robot=robot,
            )
        if robot.connection.state != 'connected':
            raise ConnectionServiceError(
                'DEVICE_NOT_CONNECTED',
                'CL-USV 尚未连接',
                robot=robot,
            )

        managed = self._network_sessions.get(robot_id)
        if (
            robot.connection.activeMethod != 'network'
            or robot.connection.dataMode != 'live'
            or not managed
            or not managed.ready
            or not managed.transport.connected
        ):
            raise ConnectionServiceError(
                'RELAY_STATE_UNAVAILABLE',
                'CL-USV 当前没有可用的继电器通信会话',
                robot=robot,
            )
        if robot.relayEnabled is None:
            raise ConnectionServiceError(
                'RELAY_STATE_UNAVAILABLE',
                '尚未收到 CL-USV 继电器状态',
                robot=robot,
            )

        async with managed.relay_command_lock:
            current = self._network_sessions.get(robot_id)
            robot = self.state.get_robot(robot_id)
            if (
                current is not managed
                or managed.closing
                or not managed.ready
                or not managed.transport.connected
                or not robot
                or robot.connection.state != 'connected'
            ):
                raise ConnectionServiceError(
                    'DEVICE_NOT_CONNECTED',
                    'CL-USV 连接已中断',
                    robot=robot,
                )
            if robot.relayEnabled is None:
                raise ConnectionServiceError(
                    'RELAY_STATE_UNAVAILABLE',
                    '尚未收到 CL-USV 继电器状态',
                    robot=robot,
                )
            if robot.relayEnabled == enabled:
                return robot

            confirmation: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            managed.relay_confirmation = (enabled, confirmation)
            action = '开启' if enabled else '关闭'
            try:
                try:
                    await managed.transport.publish_bool(self.usv_relay_command_topic, enabled)
                except Exception as exc:
                    message = str(exc) or exc.__class__.__name__
                    self.state.append_log('通信', robot_id, f'电磁固定指令发布失败：{message}')
                    await self.broadcast_log_snapshots()
                    raise ConnectionServiceError(
                        'RELAY_COMMAND_PUBLISH_FAILED',
                        f'电磁固定指令发布失败：{message}',
                        status_code=502,
                        robot=self.state.get_robot(robot_id),
                    ) from exc

                self.state.append_log('操作', robot_id, f'电磁固定{action}指令已发送')
                await self.broadcast_log_snapshots()
                try:
                    await asyncio.wait_for(
                        confirmation,
                        timeout=self.usv_relay_confirmation_timeout_sec,
                    )
                except TimeoutError as exc:
                    raise ConnectionServiceError(
                        'RELAY_CONFIRMATION_TIMEOUT',
                        f'等待电磁固定{action}状态确认超时',
                        status_code=504,
                        robot=self.state.get_robot(robot_id),
                    ) from exc

                confirmed = self.state.get_robot(robot_id)
                if not confirmed:
                    raise ConnectionServiceError('ROBOT_NOT_FOUND', '设备不存在', status_code=404)
                self.state.append_log('操作', robot_id, f'电磁固定已{action}')
                await self.broadcast_log_snapshots()
                return confirmed
            finally:
                current_confirmation = managed.relay_confirmation
                if current_confirmation and current_confirmation[1] is confirmation:
                    managed.relay_confirmation = None

    async def _open_live_session(self, robot_id: str, profile: NetworkConnectionProfile) -> Robot:
        generation = self._next_generation(robot_id)
        loop = self._loop or asyncio.get_running_loop()
        first_message: asyncio.Future[tuple[ParsedRosState, float, float]] = loop.create_future()
        transport = self._ros_session_factory(
            str(profile.host),
            profile.port,
            self.ros_topic_state,
            self.ros_connect_timeout_sec,
        )
        managed = NetworkSession(
            profile=profile,
            transport=transport,
            generation=generation,
            first_message=first_message,
            relay_command_lock=asyncio.Lock(),
        )
        self._network_sessions[robot_id] = managed

        def on_message(message: dict[str, Any]) -> None:
            if self._loop and not self._stopping:
                self._loop.call_soon_threadsafe(self._dispatch_ros_message, robot_id, generation, message)

        def on_close(reason: str) -> None:
            if self._loop and not self._stopping:
                self._loop.call_soon_threadsafe(self._dispatch_ros_close, robot_id, generation, reason)

        try:
            await asyncio.wait_for(
                transport.open(on_message, on_close),
                timeout=self.ros_connect_timeout_sec + 0.5,
            )
            try:
                parsed, received_at, received_monotonic = await asyncio.wait_for(
                    first_message,
                    timeout=self.ros_first_message_timeout_sec,
                )
            except TimeoutError as exc:
                raise ConnectionServiceError(
                    "ROSBRIDGE_TOPIC_TIMEOUT",
                    f"ROSBridge 已连接，但 {self.ros_topic_state} 在 {self.ros_first_message_timeout_sec:g} 秒内没有合法数据",
                ) from exc

            if self._network_sessions.get(robot_id) is not managed:
                raise ConnectionServiceError("ROSBRIDGE_CONNECTION_REFUSED", "ROSBridge 会话已被替换")
            connected = self.state.mark_connected(robot_id, profile, "live", "virtual")
            managed.ready = True
            managed.last_valid_monotonic = received_monotonic
            self.state.apply_live_telemetry(
                robot_id,
                parsed.envelope.data,
                received_at,
                gps_fallback=parsed.gps_fallback,
            )
            if not connected:
                raise ConnectionServiceError("ROBOT_NOT_FOUND", "设备不存在", status_code=404)
            return self.state.get_robot(robot_id) or connected
        except ConnectionServiceError:
            await self._discard_network_session(robot_id, generation)
            raise
        except TimeoutError as exc:
            await self._discard_network_session(robot_id, generation)
            raise ConnectionServiceError(
                "ROSBRIDGE_CONNECTION_TIMEOUT",
                f"连接 ROSBridge {profile.host}:{profile.port} 超时",
            ) from exc
        except ConnectionRefusedError as exc:
            await self._discard_network_session(robot_id, generation)
            raise ConnectionServiceError(
                "ROSBRIDGE_CONNECTION_REFUSED",
                f"ROSBridge {profile.host}:{profile.port} 拒绝连接",
            ) from exc
        except OSError as exc:
            await self._discard_network_session(robot_id, generation)
            raise ConnectionServiceError(
                "ROSBRIDGE_CONNECTION_REFUSED",
                f"无法连接 ROSBridge {profile.host}:{profile.port}：{exc}",
            ) from exc
        except Exception as exc:
            await self._discard_network_session(robot_id, generation)
            message = str(exc) or exc.__class__.__name__
            normalized = f"{exc.__class__.__name__} {message}".casefold()
            if "timeout" in normalized or "failed to connect to ros" in normalized:
                raise ConnectionServiceError(
                    "ROSBRIDGE_CONNECTION_TIMEOUT",
                    f"连接 ROSBridge {profile.host}:{profile.port} 超时：{message}",
                ) from exc
            code = "ROSBRIDGE_CLIENT_UNAVAILABLE" if "roslibpy" in normalized else "ROSBRIDGE_CONNECTION_REFUSED"
            status_code = 503 if code == "ROSBRIDGE_CLIENT_UNAVAILABLE" else 409
            raise ConnectionServiceError(code, f"ROSBridge 客户端启动失败：{message}", status_code=status_code) from exc

    def _dispatch_ros_message(self, robot_id: str, generation: int, message: dict[str, Any]) -> None:
        managed = self._network_sessions.get(robot_id)
        if not managed or managed.generation != generation or managed.closing:
            return
        try:
            parsed = parse_ros_state_message(message, robot_id)
        except RosMessageError as exc:
            error = ConnectionServiceError(exc.code, exc.message)
            if not managed.first_message.done():
                managed.first_message.set_exception(error)
            elif exc.code in ("ROBOT_ID_MISMATCH", "MAVROS_DATA_UNAVAILABLE"):
                self._schedule_network_recovery(robot_id, generation, exc.code, exc.message, exc.retryable)
            elif not managed.invalid_message_logged:
                managed.invalid_message_logged = True
                self.state.append_log("通信", robot_id, f"忽略非法状态消息：{exc.message}")
                asyncio.create_task(self.broadcast_log_snapshots())
            return

        received_at = time.time()
        received_monotonic = time.monotonic()
        if not managed.first_message.done():
            managed.first_message.set_result((parsed, received_at, received_monotonic))
            return
        if not managed.ready:
            return
        managed.last_valid_monotonic = received_monotonic
        managed.invalid_message_logged = False
        updated = self.state.apply_live_telemetry(
            robot_id,
            parsed.envelope.data,
            received_at,
            gps_fallback=parsed.gps_fallback,
        )
        if updated:
            self._resolve_relay_confirmation(managed, updated.relayEnabled)
            asyncio.create_task(self.broadcast_robot_state())

    @staticmethod
    def _resolve_relay_confirmation(managed: NetworkSession, relay_enabled: bool | None) -> None:
        confirmation = managed.relay_confirmation
        if confirmation is None or relay_enabled is None:
            return
        expected, future = confirmation
        if relay_enabled == expected and not future.done():
            future.set_result(None)

    def _reject_relay_confirmation(
        self,
        robot_id: str,
        managed: NetworkSession,
        code: str,
        message: str,
    ) -> None:
        confirmation = managed.relay_confirmation
        if confirmation is None:
            return
        _, future = confirmation
        if not future.done():
            future.set_exception(
                ConnectionServiceError(
                    code,
                    message,
                    robot=self.state.get_robot(robot_id),
                )
            )

    def _dispatch_ros_close(self, robot_id: str, generation: int, reason: str) -> None:
        managed = self._network_sessions.get(robot_id)
        if not managed or managed.generation != generation or managed.closing:
            return
        message = f"ROSBridge 连接意外关闭：{reason}"
        if not managed.first_message.done():
            managed.first_message.set_exception(ConnectionServiceError("ROSBRIDGE_CONNECTION_REFUSED", message))
            return
        self._schedule_network_recovery(robot_id, generation, "ROSBRIDGE_CONNECTION_REFUSED", message, True)

    def _schedule_network_recovery(
        self,
        robot_id: str,
        generation: int,
        code: str,
        message: str,
        retryable: bool,
    ) -> None:
        if self._stopping or robot_id in self._reconnect_tasks:
            return
        managed = self._network_sessions.get(robot_id)
        if not managed or managed.generation != generation or not managed.ready:
            return
        task = asyncio.create_task(self._recover_network_connection(robot_id, generation, code, message, retryable))
        self._reconnect_tasks[robot_id] = task

    async def _recover_network_connection(
        self,
        robot_id: str,
        generation: int,
        code: str,
        message: str,
        retryable: bool,
    ) -> None:
        current_task = asyncio.current_task()
        managed = self._network_sessions.get(robot_id)
        if not managed or managed.generation != generation:
            return
        profile = managed.profile
        try:
            await self._discard_network_session(robot_id, generation)
            if not retryable:
                await self._finalize_network_failure(robot_id, profile, code, message)
                return

            self.state.mark_connecting(robot_id, profile, preserve_last_comm=True)
            self.state.append_log("通信", robot_id, f"实时状态中断，开始自动恢复：{message}")
            await self.broadcast_snapshots()
            last_error = ConnectionServiceError(code, message)

            for attempt, delay in enumerate(self.ros_reconnect_delays_sec, start=1):
                await asyncio.sleep(delay)
                if self._stopping or self._reconnect_tasks.get(robot_id) is not current_task:
                    return
                self.state.append_log("通信", robot_id, f"自动重连第 {attempt}/{len(self.ros_reconnect_delays_sec)} 次")
                try:
                    await self._open_live_session(robot_id, profile)
                except ConnectionServiceError as exc:
                    last_error = exc
                    if exc.code in ("ROBOT_ID_MISMATCH", "ROS_MESSAGE_INVALID"):
                        break
                    continue
                self.state.append_log("通信", robot_id, "ROSBridge 实时状态已自动恢复")
                await self.broadcast_snapshots()
                return

            await self._finalize_network_failure(robot_id, profile, last_error.code, last_error.message)
        except asyncio.CancelledError:
            raise
        finally:
            if self._reconnect_tasks.get(robot_id) is current_task:
                self._reconnect_tasks.pop(robot_id, None)

    async def _finalize_network_failure(
        self,
        robot_id: str,
        profile: NetworkConnectionProfile,
        code: str,
        message: str,
    ) -> None:
        await self._discard_network_session(robot_id)
        self._release_network_endpoint(robot_id, profile)
        alarm_message = f"设备实时状态连接中断：{message}"
        self.state.mark_connection_error(robot_id, code, message, preserve_last_comm=True)
        self.state.push_alarm("严重", robot_id, alarm_message, attach_to_robot=False)
        await self.broadcast_snapshots()

    async def _monitor_network_connections(self) -> None:
        while True:
            await asyncio.sleep(self.ros_watchdog_interval_sec)
            now = time.monotonic()
            for robot_id, managed in list(self._network_sessions.items()):
                if not managed.ready or managed.last_valid_monotonic is None:
                    continue
                if now - managed.last_valid_monotonic > self.ros_stale_timeout_sec:
                    self._schedule_network_recovery(
                        robot_id,
                        managed.generation,
                        "TELEMETRY_STALE",
                        f"连续 {self.ros_stale_timeout_sec:g} 秒未收到合法 MAVROS 状态",
                        True,
                    )

    async def _discard_network_session(self, robot_id: str, generation: int | None = None) -> None:
        managed = self._network_sessions.get(robot_id)
        if not managed or (generation is not None and managed.generation != generation):
            return
        self._network_sessions.pop(robot_id, None)
        managed.closing = True
        self._reject_relay_confirmation(
            robot_id,
            managed,
            'DEVICE_NOT_CONNECTED',
            'CL-USV 连接已中断',
        )
        with suppress(Exception):
            await managed.transport.close()

    async def _cancel_reconnect(self, robot_id: str) -> None:
        task = self._reconnect_tasks.pop(robot_id, None)
        if not task or task is asyncio.current_task():
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    def _claim_network_endpoint(self, robot_id: str, profile: NetworkConnectionProfile) -> None:
        endpoint = self._network_endpoint(profile)
        owner = self._endpoint_owners.get(endpoint)
        if owner and owner != robot_id:
            raise ConnectionServiceError("NETWORK_ENDPOINT_IN_USE", f"网络端点 {endpoint} 已分配给设备 {owner}")
        self._endpoint_owners[endpoint] = robot_id

    def _release_network_endpoint(self, robot_id: str, profile: NetworkConnectionProfile) -> None:
        endpoint = self._network_endpoint(profile)
        if self._endpoint_owners.get(endpoint) == robot_id:
            self._endpoint_owners.pop(endpoint, None)

    @staticmethod
    def _network_endpoint(profile: NetworkConnectionProfile) -> str:
        return f"{profile.host}:{profile.port}"

    def _next_generation(self, robot_id: str) -> int:
        generation = self._generations.get(robot_id, 0) + 1
        self._generations[robot_id] = generation
        return generation

    def _open_serial_sync(self, robot_id: str, profile: SerialConnectionProfile) -> Any:
        normalized_port = self._normalize_port(profile.port)
        owner = self._port_owners.get(normalized_port)
        if owner and owner != robot_id:
            raise ConnectionServiceError("SERIAL_PORT_IN_USE", f"{profile.port} 已分配给设备 {owner}")

        available_ports = {self._normalize_port(item.port) for item in self.list_serial_ports_sync()}
        if normalized_port not in available_ports:
            raise ConnectionServiceError("SERIAL_PORT_NOT_FOUND", f"未找到串口 {profile.port}")
        if self._serial_factory is None:
            raise ConnectionServiceError("SERIAL_OPEN_FAILED", "pyserial 未安装，无法打开串口")

        try:
            return self._serial_factory(
                port=profile.port,
                baudrate=profile.baudRate,
                bytesize=getattr(serial_module, "EIGHTBITS", 8),
                parity=getattr(serial_module, "PARITY_NONE", "N"),
                stopbits=getattr(serial_module, "STOPBITS_ONE", 1),
                timeout=0,
                write_timeout=0,
            )
        except Exception as exc:
            serial_exception_type = getattr(serial_module, "SerialException", None)
            error_message = str(exc)
            busy_markers = ("access is denied", "permission", "busy", "in use", "拒绝访问", "占用")
            if isinstance(exc, PermissionError) or any(marker in error_message.casefold() for marker in busy_markers):
                raise ConnectionServiceError("SERIAL_PORT_BUSY_OR_DENIED", f"{profile.port} 已被占用或无访问权限") from exc
            if serial_exception_type and isinstance(exc, serial_exception_type):
                raise ConnectionServiceError("SERIAL_OPEN_FAILED", f"打开串口 {profile.port} 失败：{error_message}") from exc
            raise ConnectionServiceError("SERIAL_OPEN_FAILED", f"打开串口 {profile.port} 失败：{error_message}") from exc

    async def _monitor_serial_connections(self) -> None:
        while True:
            await asyncio.sleep(self.monitor_interval_sec)
            if not self._serial_sessions:
                continue
            try:
                available_ports = {self._normalize_port(item.port) for item in await self.list_serial_ports()}
            except ConnectionServiceError:
                continue
            failed: list[tuple[str, str]] = []
            for robot_id, session in list(self._serial_sessions.items()):
                try:
                    is_open = bool(session.handle.is_open)
                except Exception:
                    is_open = False
                if not is_open:
                    failed.append((robot_id, "串口句柄已关闭"))
                elif self._normalize_port(session.port) not in available_ports:
                    failed.append((robot_id, f"串口 {session.port} 已从系统移除"))
            for robot_id, reason in failed:
                await self._handle_unexpected_serial_disconnect(robot_id, reason)

    async def _handle_unexpected_serial_disconnect(self, robot_id: str, reason: str) -> None:
        async with self._robot_lock(robot_id):
            session = self._serial_sessions.pop(robot_id, None)
            if not session:
                return
            self._port_owners.pop(self._normalize_port(session.port), None)
            await asyncio.to_thread(self._close_serial_handle, session.handle)
            message = f"串口连接意外中断：{reason}"
            self.state.mark_connection_error(robot_id, "SERIAL_CONNECTION_LOST", message, preserve_last_comm=True)
            self.state.push_alarm("严重", robot_id, message, attach_to_robot=False)
            await self.broadcast_snapshots()

    async def broadcast_robot_state(self) -> None:
        await telemetry_manager.broadcast(
            {"type": "robot_state", "data": [robot.model_dump(mode="json") for robot in self.state.list_robots()]}
        )

    async def broadcast_log_snapshots(self) -> None:
        await telemetry_manager.broadcast(
            {"type": "log_snapshot", "data": [item.model_dump(mode="json") for item in self.state.list_logs()]}
        )

    async def broadcast_snapshots(self) -> None:
        await self.broadcast_robot_state()
        await self.broadcast_log_snapshots()
        await telemetry_manager.broadcast(
            {"type": "alarm_snapshot", "data": [item.model_dump(mode="json") for item in self.state.list_alarms()]}
        )

    @staticmethod
    def _close_serial_handle(handle: Any) -> None:
        with suppress(Exception):
            if bool(getattr(handle, "is_open", True)):
                handle.close()

    @staticmethod
    def _normalize_port(port: str) -> str:
        return port.strip().casefold()

    @staticmethod
    def _method_label(profile: ConnectionProfile) -> str:
        return "串口" if profile.method == "serial" else "网络"


connection_manager: ConnectionManager | None = None
