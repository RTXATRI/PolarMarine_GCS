from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from polarmarine_gcs.domain.links import LinkProfile

DriverEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class DriverGateway(Protocol):
    def set_event_handler(self, handler: DriverEventHandler) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def start_link(
        self,
        profile: LinkProfile,
        *,
        expected_device_id: str,
        requested_capabilities: frozenset[str],
    ) -> None: ...

    async def stop_link(self, profile: LinkProfile) -> None: ...

    async def send_command(self, profile: LinkProfile, message: dict[str, Any]) -> None: ...

    async def debug_request(self, driver: str, request: dict[str, Any]) -> dict[str, Any]: ...
