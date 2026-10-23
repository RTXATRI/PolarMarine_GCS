# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

repo = Path(SPEC).resolve().parents[2]
backend = repo / "backend"
source = backend / "src"

datas = [
    (str(backend / "alembic.ini"), "."),
    (str(backend / "alembic"), "alembic"),
    (str(repo / "dist"), "frontend"),
    (str(repo / "contracts"), "contracts"),
]
hiddenimports = collect_submodules("uvicorn") + collect_submodules("mcap")
for package in ("sqlalchemy", "alembic", "zeroconf"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    hiddenimports += package_hidden

core_analysis = Analysis(
    [str(repo / "packaging" / "windows" / "core_entry.py")],
    pathex=[str(source), str(backend)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
core_pyz = PYZ(core_analysis.pure)
core = EXE(
    core_pyz,
    core_analysis.scripts,
    [],
    exclude_binaries=True,
    name="PolarMarine-GCS",
    console=False,
)


def driver_executable(kind):
    analysis = Analysis(
        [str(backend / "drivers" / kind / "main.py")],
        pathex=[str(source), str(backend)],
        binaries=[],
        datas=[],
        hiddenimports=["serial", "serial.tools.list_ports", "websockets.sync.client", "zeroconf"],
        noarchive=False,
    )
    archive = PYZ(analysis.pure)
    executable = EXE(
        archive,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name=f"polarmarine-{kind}-driver",
        console=False,
    )
    return analysis, executable


driver_builds = [driver_executable(kind) for kind in ("ros1", "ros2", "serial_json", "simulator")]
all_binaries = [core_analysis.binaries]
all_datas = [core_analysis.datas]
executables = [core]
for analysis, executable in driver_builds:
    all_binaries.append(analysis.binaries)
    all_datas.append(analysis.datas)
    executables.append(executable)

coll = COLLECT(
    *executables,
    *all_binaries,
    *all_datas,
    name="PolarMarine_GCS",
)
