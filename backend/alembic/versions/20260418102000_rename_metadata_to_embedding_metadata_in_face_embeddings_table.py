"""rename metadata to embedding_metadata in face_embeddings table

Revision ID: 20260418102000
Revises: 0002_recog_dedupe_key
Create Date: 2026-04-18 10:20:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260418102000"
down_revision = "0002_recog_dedupe_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("face_embeddings", "metadata", new_column_name="embedding_metadata")


def downgrade() -> None:
    op.alter_column("face_embeddings", "embedding_metadata", new_column_name="metadata")