from __future__ import annotations

import ast
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SOURCE = REPOSITORY_ROOT / "backend" / "src" / "polarmarine_gcs"
FRONTEND_SOURCE = REPOSITORY_ROOT / "src"


def test_domain_has_no_framework_or_hardware_imports() -> None:
    forbidden_roots = {"fastapi", "pydantic", "sqlalchemy", "serial", "rospy", "rclpy"}
    violations: list[str] = []
    for path in (BACKEND_SOURCE / "domain").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            for module in imported:
                if module.split(".", maxsplit=1)[0] in forbidden_roots:
                    violations.append(f"{path.name}:{node.lineno}:{module}")
    assert violations == []


def test_removed_compatibility_and_browser_business_simulation_cannot_return() -> None:
    forbidden = {
        "dataMode": "legacy live/simulated field",
        "commandMode": "legacy command field",
        "/api/robots": "legacy API",
        "mock_simulator": "implicit simulator",
        "virtual_tasks": "browser/core virtual task implementation",
        "Math.random(": "browser business simulation",
    }
    violations: list[str] = []
    paths = list(BACKEND_SOURCE.rglob("*.py")) + list(FRONTEND_SOURCE.rglob("*.ts"))
    paths += list(FRONTEND_SOURCE.rglob("*.vue"))
    for path in paths:
        if path.name == "generated.ts":
            continue
        content = path.read_text(encoding="utf-8")
        for token, reason in forbidden.items():
            if token in content:
                violations.append(f"{path.relative_to(REPOSITORY_ROOT)}: {reason}")
    assert violations == []


def test_device_seed_ids_are_not_used_as_behavior_branches() -> None:
    pattern = re.compile(r"\b(if|elif|case)\b[^\n]*(Hexa-UAV|CL-USV|SmartDock-1)")
    violations: list[str] = []
    paths = list(BACKEND_SOURCE.rglob("*.py")) + list(FRONTEND_SOURCE.rglob("*.ts"))
    paths += list(FRONTEND_SOURCE.rglob("*.vue"))
    for path in paths:
        if pattern.search(path.read_text(encoding="utf-8")):
            violations.append(str(path.relative_to(REPOSITORY_ROOT)))
    assert violations == []


def test_legacy_source_trees_and_committed_backup_are_absent() -> None:
    legacy_backend = REPOSITORY_ROOT / "backend" / "app"
    assert not legacy_backend.exists() or not any(
        path.is_file() for path in legacy_backend.rglob("*")
    )
    assert not (REPOSITORY_ROOT / "PolarMarine_GCS.zip").exists()
    for directory in ("components", "views", "stores", "services"):
        legacy_frontend = FRONTEND_SOURCE / directory
        assert not legacy_frontend.exists() or not any(
            path.is_file() for path in legacy_frontend.rglob("*")
        )
