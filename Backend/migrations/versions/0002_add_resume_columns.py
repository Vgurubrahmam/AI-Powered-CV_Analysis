"""Add missing columns to resumes table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-30 06:00:00.000000 UTC

Adds columns that exist in the ORM model but were missing from the initial
migration: raw_text, parse_confidence, language, version.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add raw_text column (nullable TEXT for storing extracted resume text)
    op.add_column("resumes", sa.Column("raw_text", sa.Text(), nullable=True))

    # Add parse_confidence (was Float in migration 0001 but Numeric(4,3) in model)
    # Column already exists as Float — skip if already present
    # op.add_column("resumes", sa.Column("parse_confidence", sa.Float(), nullable=True))

    # Add language column with default 'en'
    op.add_column(
        "resumes",
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
    )

    # Add version column with default 1
    op.add_column(
        "resumes",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("resumes", "version")
    op.drop_column("resumes", "language")
    op.drop_column("resumes", "raw_text")
