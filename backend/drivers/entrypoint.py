from __future__ import annotations

from drivers.runtime import DriverHost, create_adapter


def run(kind: str) -> int:
    host = DriverHost(kind)
    host.adapter = create_adapter(kind, host)
    return host.run()
