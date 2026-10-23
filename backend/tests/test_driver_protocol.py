from __future__ import annotations

from datetime import UTC, datetime

from drivers.runtime import _canonical_validation_error

from polarmarine_gcs.bootstrap.settings import CONTRACTS_ROOT
from polarmarine_gcs.domain.links import DriverKind
from polarmarine_gcs.infrastructure.drivers.supervisor import _load_driver_manifests


def _envelope() -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "deviceId": "device-1",
        "messageId": "message-1",
        "sequence": 0xFFFFFFFF,
        "sentAt": datetime.now(UTC).isoformat(),
        "type": "heartbeat",
        "correlationId": None,
        "payload": {},
    }


def test_canonical_envelope_requires_versioned_identity_and_uint32_sequence() -> None:
    assert _canonical_validation_error(_envelope()) is None
    invalid = _envelope()
    invalid["sequence"] = -1
    assert "unsigned 32-bit" in str(_canonical_validation_error(invalid))
    invalid = _envelope()
    invalid["sentAt"] = "2026-07-23T10:00:00"
    assert "timezone" in str(_canonical_validation_error(invalid))


def test_all_supported_drivers_have_versioned_plugin_manifests() -> None:
    manifests = _load_driver_manifests(CONTRACTS_ROOT / "driver_plugins")
    assert set(manifests) == set(DriverKind)
    assert manifests[DriverKind.ROS1].supports == {
        "formalControl",
        "debugConsole",
        "identityDiscovery",
    }
    assert manifests[DriverKind.SERIAL_JSON].executable.endswith("serial_json-driver.exe")
