"""Record successful Helm migration and seed runs."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create durable completion markers for Helm release revisions."""
    op.create_table(
        "lifecycle_completions",
        sa.Column("installation_id", sa.String(32), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.CheckConstraint("revision > 0", name="ck_lifecycle_revision_positive"),
    )


def downgrade() -> None:
    """Remove completion markers without changing recipe data."""
    op.drop_table("lifecycle_completions")
