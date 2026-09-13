"""Version rating-limited drafts without changing saved teams.

Revision ID: f31b72d4c905
Revises: e20a91d8f672
"""

import sqlalchemy as sa
from alembic import op

revision = "f31b72d4c905"
down_revision = "e20a91d8f672"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("drafts") as batch:
        batch.add_column(
            sa.Column("selection_ruleset", sa.String(40), nullable=False, server_default="open-v1")
        )
    with op.batch_alter_table("drafts") as batch:
        batch.alter_column("selection_ruleset", server_default=None)


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM drafts WHERE selection_ruleset != 'open-v1'")
    ):
        raise RuntimeError("Cannot downgrade while rating-limited drafts exist")
    with op.batch_alter_table("drafts") as batch:
        batch.drop_column("selection_ruleset")
