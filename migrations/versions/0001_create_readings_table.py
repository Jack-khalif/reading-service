"""create readings table

Revision ID: 0001
Revises:
Create Date: 2026-10-15 20:19:41.295191

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "readings",
        # The PRIMARY KEY is what makes ingest idempotent: it's the target
        # of `ON CONFLICT (reading_id) DO NOTHING`.
        sa.Column("reading_id", sa.Text(), primary_key=True),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        # Real timestamps (not ISO strings, as in the SQLite version), so
        # ordering and range filters compare instants, not characters.
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("arrived_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("clock_anomaly", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "idx_device_metric_time",
        "readings",
        ["device_id", "metric", "recorded_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_device_metric_time", table_name="readings")
    op.drop_table("readings")
