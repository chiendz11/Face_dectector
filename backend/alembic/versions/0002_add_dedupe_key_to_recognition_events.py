from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_dedupe_key_to_recognition_events"
down_revision = "0001_create_employees_and_recognition_events"
branch_labels = None

def upgrade() -> None:
    op.add_column(
        "recognition_events",
        sa.Column("dedupe_key", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_recognition_events_dedupe_key",
        "recognition_events",
        ["dedupe_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_recognition_events_dedupe_key", table_name="recognition_events")
    op.drop_column("recognition_events", "dedupe_key")
