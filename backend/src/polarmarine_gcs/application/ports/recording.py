from __future__ import annotations

from typing import Protocol

from polarmarine_gcs.domain.recordings import Recording


class RecordingGateway(Protocol):
    async def begin(self, mission_run_id: str, device_ids: frozenset[str]) -> Recording: ...

    async def finish(
        self, mission_run_id: str, *, interrupted: bool = False
    ) -> Recording | None: ...
