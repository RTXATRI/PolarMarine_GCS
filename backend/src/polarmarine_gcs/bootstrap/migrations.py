from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from polarmarine_gcs.bootstrap.settings import RESOURCE_ROOT


def upgrade_database(
    database_url: str,
    backup_directory: Path,
    *,
    backup_retention_count: int = 5,
) -> None:
    """Back up an existing SQLite DB when needed, then upgrade it to Alembic head."""

    configuration = Config(str(RESOURCE_ROOT / "alembic.ini"))
    configuration.set_main_option("script_location", str(RESOURCE_ROOT / "alembic"))
    configuration.attributes["database_url"] = database_url
    scripts = ScriptDirectory.from_config(configuration)
    head_revision = scripts.get_current_head()
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            current_revision = MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
    if current_revision != head_revision:
        _backup_sqlite_database(
            database_url,
            backup_directory,
            retention_count=backup_retention_count,
        )
    command.upgrade(configuration, "head")


def _backup_sqlite_database(
    database_url: str,
    backup_directory: Path,
    *,
    retention_count: int,
) -> Path | None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    database_path = Path(url.database).resolve()
    if not database_path.is_file() or database_path.stat().st_size == 0:
        return None
    backup_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_directory / f"{database_path.stem}-{timestamp}{database_path.suffix}.bak"
    shutil.copy2(database_path, destination)
    backups = sorted(
        backup_directory.glob(f"{database_path.stem}-*{database_path.suffix}.bak"),
        key=lambda item: item.stat().st_mtime_ns,
        reverse=True,
    )
    for stale_backup in backups[retention_count:]:
        stale_backup.unlink()
    return destination
