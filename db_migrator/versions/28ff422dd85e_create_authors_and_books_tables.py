"""create authors and books tables

Revision ID: 28ff422dd85e
Revises:
Create Date: 2026-09-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "28ff422dd85e"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

book_type_enum = postgresql.ENUM(
    "fiction",
    "non_fiction",
    "biography",
    "science",
    "history",
    "poetry",
    "other",
    name="booktype",
)


def upgrade() -> None:
    book_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "authors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("bio", sa.String(), nullable=True),
    )

    op.create_table(
        "books",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("authors.id"),
            nullable=False,
        ),
        sa.Column("book_type", book_type_enum, nullable=False),
        sa.Column("isbn", sa.String(), nullable=True),
        sa.Column("published_year", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("books")
    op.drop_table("authors")
    book_type_enum.drop(op.get_bind(), checkfirst=True)
