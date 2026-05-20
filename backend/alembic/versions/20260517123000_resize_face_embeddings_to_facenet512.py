"""resize face embeddings for Facenet512

Revision ID: 20260517123000
Revises: 20260418102000
Create Date: 2026-05-17 12:30:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260517123000"
down_revision = "20260418102000"
branch_labels = None
depends_on = None


def _ensure_empty_face_embeddings_table() -> None:
    bind = op.get_bind()
    count = bind.execute(sa.text("SELECT COUNT(*) FROM face_embeddings")).scalar()
    if count:
        raise RuntimeError(
            "Cannot change face_embeddings.embedding vector dimension while enrolled "
            "face embeddings exist. Back up the database, delete/re-enroll embeddings, "
            "then rerun the migration."
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _ensure_empty_face_embeddings_table()
    op.execute("ALTER TABLE face_embeddings ALTER COLUMN embedding TYPE vector(512)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    _ensure_empty_face_embeddings_table()
    op.execute("ALTER TABLE face_embeddings ALTER COLUMN embedding TYPE vector(16)")
