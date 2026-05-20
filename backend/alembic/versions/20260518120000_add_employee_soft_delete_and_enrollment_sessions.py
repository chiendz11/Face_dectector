"""add employee soft delete and enrollment sessions

Revision ID: 20260518120000
Revises: 20260517123000
Create Date: 2026-05-18 12:00:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20260518120000"
down_revision = "20260517123000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "employees",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column("employees", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "enrollment_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("employee_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("used_by", sa.String(length=128), nullable=True),
        sa.Column("device_name", sa.String(length=64), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_enrollment_sessions_token_hash", "enrollment_sessions", ["token_hash"])
    op.create_index("ix_enrollment_sessions_employee_code", "enrollment_sessions", ["employee_code"])


def downgrade() -> None:
    op.drop_index("ix_enrollment_sessions_employee_code", table_name="enrollment_sessions")
    op.drop_index("ix_enrollment_sessions_token_hash", table_name="enrollment_sessions")
    op.drop_table("enrollment_sessions")

    op.drop_column("employees", "deleted_at")
    op.drop_column("employees", "updated_at")
    op.drop_column("employees", "active")
