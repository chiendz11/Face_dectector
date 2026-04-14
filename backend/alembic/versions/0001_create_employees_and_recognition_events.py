from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "0001_create_employees_and_recognition_events"
down_revision = None
branch_labels = None
def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("employee_code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=128), nullable=False),
        sa.Column("department", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_employees_employee_code", "employees", ["employee_code"])

    op.create_table(
        "recognition_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("employee_code", sa.String(length=32), nullable=True),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("device_name", sa.String(length=64), nullable=True),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("snapshot_url", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "face_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("employee_code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("embedding", Vector(16), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_face_embeddings_employee_code", "face_embeddings", ["employee_code"])
