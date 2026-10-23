"""Persist command results and immutable mission run snapshots.

Revision ID: 20260723_0002
Revises: 20260723_0001
Create Date: 2026-07-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260723_0002"
down_revision = "20260723_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "mission_plan_versions" not in inspector.get_table_names():
        op.create_table(
            "mission_plan_versions",
            sa.Column("plan_id", sa.String(length=36), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("steps", sa.JSON(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["plan_id"], ["mission_plans.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("plan_id", "version"),
        )
    command_columns = {item["name"] for item in inspector.get_columns("commands")}
    if "result" not in command_columns:
        op.add_column(
            "commands",
            sa.Column("result", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )
    command_unique_names = {
        item["name"] for item in inspector.get_unique_constraints("commands") if item["name"]
    }
    command_index_names = {item["name"] for item in inspector.get_indexes("commands")}
    if "uq_command_key" not in command_unique_names | command_index_names:
        op.create_index(
            "uq_command_key",
            "commands",
            ["device_id", "idempotency_key"],
            unique=True,
        )

    mission_run_columns = {item["name"] for item in inspector.get_columns("mission_runs")}
    if "plan_steps" not in mission_run_columns:
        op.add_column(
            "mission_runs",
            sa.Column("plan_steps", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "uq_command_key" in {item["name"] for item in inspector.get_indexes("commands")}:
        op.drop_index("uq_command_key", table_name="commands")
    mission_run_columns = {item["name"] for item in inspector.get_columns("mission_runs")}
    if "plan_steps" in mission_run_columns:
        op.drop_column("mission_runs", "plan_steps")

    command_columns = {item["name"] for item in inspector.get_columns("commands")}
    if "result" in command_columns:
        op.drop_column("commands", "result")

    inspector = sa.inspect(connection)
    if "mission_plan_versions" in inspector.get_table_names():
        op.drop_table("mission_plan_versions")
