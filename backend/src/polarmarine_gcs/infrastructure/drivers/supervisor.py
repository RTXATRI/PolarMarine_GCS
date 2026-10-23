from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polarmarine_gcs.application.ports.drivers import DriverEventHandler, DriverGateway
from polarmarine_gcs.domain.common import UnavailableError, new_id, utc_now
from polarmarine_gcs.domain.links import DriverKind, LinkProfile

from .framing import FrameError, IpcFrameDecoder, encode_ipc_message

LOGGER = logging.getLogger(__name__)


class DriverSupervisor(DriverGateway):
    def __init__(
        self,
        driver_script: Path,
        source_root: Path,
        *,
        manifest_directory: Path,
        executable_directory: Path | None = None,
        heartbeat_timeout_seconds: float = 3.0,
    ) -> None:
        self.driver_script = driver_script
        self.source_root = source_root
        self.manifests = _load_driver_manifests(manifest_directory)
        self.executable_directory = executable_directory
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._event_handler: DriverEventHandler | None = None
        self._workers: dict[DriverKind, _DriverWorker] = {}
        self._started = False

    def set_event_handler(self, handler: DriverEventHandler) -> None:
        self._event_handler = handler

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False
        workers = list(self._workers.values())
        self._workers.clear()
        await asyncio.gather(*(worker.stop() for worker in workers), return_exceptions=True)

    async def start_link(
        self,
        profile: LinkProfile,
        *,
        expected_device_id: str,
        requested_capabilities: frozenset[str],
    ) -> None:
        worker = self._worker(profile.driver)
        request = {
            "schemaVersion": "1.0",
            "messageId": new_id(),
            "type": "link.start",
            "sentAt": utc_now().isoformat(),
            "payload": {
                "linkId": profile.id,
                "deviceId": profile.device_id,
                "expectedDeviceId": expected_device_id,
                "config": profile.config,
                "requestedCapabilities": sorted(requested_capabilities),
            },
        }
        worker.desired_links[profile.id] = request
        await worker.ensure_running()
        await worker.send(request)

    async def stop_link(self, profile: LinkProfile) -> None:
        worker = self._workers.get(profile.driver)
        if worker is None:
            return
        worker.desired_links.pop(profile.id, None)
        if worker.is_running:
            await worker.send(
                {
                    "schemaVersion": "1.0",
                    "messageId": new_id(),
                    "type": "link.stop",
                    "sentAt": utc_now().isoformat(),
                    "payload": {"linkId": profile.id, "deviceId": profile.device_id},
                }
            )

    async def send_command(self, profile: LinkProfile, message: dict[str, Any]) -> None:
        worker = self._workers.get(profile.driver)
        if worker is None or not worker.is_running:
            raise UnavailableError(f"Driver {profile.driver.value} is not running")
        await worker.send(
            {
                "schemaVersion": "1.0",
                "messageId": new_id(),
                "type": "command.send",
                "sentAt": utc_now().isoformat(),
                "payload": {"linkId": profile.id, "message": message},
            }
        )

    async def debug_request(self, driver: str, request: dict[str, Any]) -> dict[str, Any]:
        try:
            kind = DriverKind(driver)
        except ValueError as exc:
            raise UnavailableError(f"Unknown driver {driver}") from exc
        worker = self._worker(kind)
        await worker.ensure_running()
        return await worker.request_debug(request)

    def _worker(self, kind: DriverKind) -> _DriverWorker:
        if not self._started:
            raise UnavailableError("Driver supervisor has not started")
        worker = self._workers.get(kind)
        if worker is None:
            worker = _DriverWorker(
                kind=kind,
                script=self.driver_script,
                source_root=self.source_root,
                executable=self._packaged_executable(kind),
                event_handler=self._dispatch_event,
                heartbeat_timeout_seconds=self.heartbeat_timeout_seconds,
            )
            self._workers[kind] = worker
        return worker

    def _packaged_executable(self, kind: DriverKind) -> Path | None:
        if self.executable_directory is None:
            return None
        executable = self.executable_directory / self.manifests[kind].executable
        if not executable.is_file():
            raise UnavailableError(f"Packaged driver executable is missing: {executable}")
        return executable

    async def _dispatch_event(self, message: dict[str, Any]) -> None:
        if self._event_handler:
            await self._event_handler(message)


@dataclass(frozen=True, slots=True)
class DriverManifest:
    kind: DriverKind
    display_name: str
    executable: str
    supports: frozenset[str]
    configuration: dict[str, Any]


def _load_driver_manifests(directory: Path) -> dict[DriverKind, DriverManifest]:
    manifests: dict[DriverKind, DriverManifest] = {}
    if not directory.is_dir():
        raise UnavailableError(f"Driver manifest directory is missing: {directory}")
    for path in sorted(directory.glob("*.json")):
        if path.name == "manifest.schema.json":
            continue
        try:
            raw: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise UnavailableError(f"Cannot read driver manifest {path.name}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("schemaVersion") != "1.0":
            raise UnavailableError(f"Driver manifest {path.name} has an unsupported schema")
        try:
            kind = DriverKind(str(raw["id"]))
        except (KeyError, ValueError) as exc:
            raise UnavailableError(f"Driver manifest {path.name} has an invalid id") from exc
        display_name = raw.get("displayName")
        executable = raw.get("executable")
        supports_raw = raw.get("supports")
        configuration = raw.get("configuration")
        if not isinstance(display_name, str) or not display_name:
            raise UnavailableError(f"Driver manifest {path.name} has no display name")
        if (
            not isinstance(executable, str)
            or not executable.endswith(".exe")
            or Path(executable).name != executable
        ):
            raise UnavailableError(f"Driver manifest {path.name} has an unsafe executable")
        support_keys = {"formalControl", "debugConsole", "identityDiscovery"}
        if not isinstance(supports_raw, dict) or any(
            not isinstance(supports_raw.get(key), bool) for key in support_keys
        ):
            raise UnavailableError(f"Driver manifest {path.name} has invalid support flags")
        if not isinstance(configuration, dict):
            raise UnavailableError(f"Driver manifest {path.name} has no configuration schema")
        if kind in manifests:
            raise UnavailableError(f"Duplicate driver manifest for {kind.value}")
        manifests[kind] = DriverManifest(
            kind=kind,
            display_name=display_name,
            executable=executable,
            supports=frozenset(key for key in support_keys if supports_raw[key]),
            configuration={str(key): value for key, value in configuration.items()},
        )
    missing = set(DriverKind).difference(manifests)
    if missing:
        names = ", ".join(sorted(item.value for item in missing))
        raise UnavailableError(f"Driver manifests are missing: {names}")
    return manifests


class _DriverWorker:
    BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0)

    def __init__(
        self,
        *,
        kind: DriverKind,
        script: Path,
        source_root: Path,
        executable: Path | None,
        event_handler: DriverEventHandler,
        heartbeat_timeout_seconds: float,
    ) -> None:
        self.kind = kind
        self.script = script
        self.source_root = source_root
        self.executable = executable
        self.event_handler = event_handler
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.process: asyncio.subprocess.Process | None = None
        self.desired_links: dict[str, dict[str, Any]] = {}
        self._write_lock = asyncio.Lock()
        self._lifecycle_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._stopping = False
        self._restart_attempt = 0
        self._last_heartbeat = 0.0
        self._debug_waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    async def ensure_running(self) -> None:
        async with self._lifecycle_lock:
            if self.is_running:
                return
            self._stopping = False
            environment = os.environ.copy()
            existing_path = environment.get("PYTHONPATH", "")
            environment["PYTHONPATH"] = str(self.source_root) + (
                os.pathsep + existing_path if existing_path else ""
            )
            creationflags = 0x08000000 if sys.platform == "win32" else 0
            command = (
                (str(self.executable),)
                if self.executable is not None
                else (
                    sys.executable,
                    "-u",
                    str(self.script),
                    "--driver",
                    self.kind.value,
                )
            )
            self.process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
                creationflags=creationflags,
            )
            self._last_heartbeat = asyncio.get_running_loop().time()
            self._spawn(self._read_stdout(), f"{self.kind.value}-stdout")
            self._spawn(self._read_stderr(), f"{self.kind.value}-stderr")
            self._spawn(self._wait_for_exit(), f"{self.kind.value}-wait")
            self._spawn(self._monitor_heartbeat(), f"{self.kind.value}-heartbeat")

    async def stop(self) -> None:
        self._stopping = True
        process = self.process
        if process and process.returncode is None:
            try:
                await self.send(
                    {
                        "schemaVersion": "1.0",
                        "messageId": new_id(),
                        "type": "driver.stop",
                        "payload": {},
                    }
                )
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except (TimeoutError, BrokenPipeError, ConnectionResetError):
                process.terminate()
                await process.wait()
        current = asyncio.current_task()
        tasks = [task for task in self._tasks if task is not current]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self.process = None
        for future in self._debug_waiters.values():
            if not future.done():
                future.set_exception(UnavailableError("Driver stopped"))
        self._debug_waiters.clear()

    async def send(self, message: dict[str, Any]) -> None:
        process = self.process
        if process is None or process.stdin is None or process.returncode is not None:
            raise UnavailableError(f"Driver {self.kind.value} is unavailable")
        frame = encode_ipc_message(message)
        async with self._write_lock:
            process.stdin.write(frame)
            await process.stdin.drain()

    async def request_debug(self, request: dict[str, Any]) -> dict[str, Any]:
        correlation_id = new_id()
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._debug_waiters[correlation_id] = future
        await self.send(
            {
                "schemaVersion": "1.0",
                "messageId": new_id(),
                "type": "debug.request",
                "correlationId": correlation_id,
                "sentAt": utc_now().isoformat(),
                "payload": request,
            }
        )
        try:
            return await asyncio.wait_for(future, timeout=10.0)
        finally:
            self._debug_waiters.pop(correlation_id, None)

    async def _read_stdout(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        decoder = IpcFrameDecoder()
        while data := await process.stdout.read(65_536):
            try:
                messages = decoder.feed(data)
            except FrameError as exc:
                LOGGER.error("Driver %s emitted invalid IPC: %s", self.kind.value, exc)
                await self._restart("INVALID_IPC")
                return
            for message in messages:
                if message.get("type") == "driver.heartbeat":
                    self._last_heartbeat = asyncio.get_running_loop().time()
                    self._restart_attempt = 0
                    continue
                if message.get("type") == "debug.response":
                    correlation_id = message.get("correlationId")
                    future = self._debug_waiters.get(str(correlation_id))
                    if future and not future.done():
                        payload = message.get("payload")
                        future.set_result(payload if isinstance(payload, dict) else {})
                    continue
                await self.event_handler(message)

    async def _read_stderr(self) -> None:
        process = self.process
        if process is None or process.stderr is None:
            return
        while line := await process.stderr.readline():
            LOGGER.warning(
                "[%s driver] %s", self.kind.value, line.decode("utf-8", errors="replace").rstrip()
            )

    async def _wait_for_exit(self) -> None:
        process = self.process
        if process is None:
            return
        return_code = await process.wait()
        if not self._stopping and self.desired_links:
            LOGGER.error("Driver %s exited with code %s", self.kind.value, return_code)
            await self._restart("DRIVER_EXITED")

    async def _monitor_heartbeat(self) -> None:
        while not self._stopping and self.is_running:
            await asyncio.sleep(1.0)
            elapsed = asyncio.get_running_loop().time() - self._last_heartbeat
            if elapsed >= self.heartbeat_timeout_seconds:
                await self._restart("DRIVER_HEARTBEAT_TIMEOUT")
                return

    async def _restart(self, reason: str) -> None:
        if self._stopping:
            return
        async with self._lifecycle_lock:
            process = self.process
            if process and process.returncode is None:
                process.terminate()
                await process.wait()
            self.process = None
        for link_id in self.desired_links:
            await self.event_handler(
                {
                    "type": "driver.link_failed",
                    "payload": {"linkId": link_id, "code": reason, "message": reason},
                }
            )
        delay = self.BACKOFF_SECONDS[min(self._restart_attempt, len(self.BACKOFF_SECONDS) - 1)]
        self._restart_attempt += 1
        await asyncio.sleep(delay)
        if self._stopping or not self.desired_links:
            return
        await self.ensure_running()
        for request in self.desired_links.values():
            await self.send(request)

    def _spawn(self, coroutine: Any, name: str) -> None:
        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
