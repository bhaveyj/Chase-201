"""Add v3 decisions and validated immutable catalog allocations without altering saves."""

import sqlalchemy as sa
from alembic import op

revision = "a42c83e5d016"
down_revision = "f31b72d4c905"
branch_labels = None
depends_on = None

OLD = "'PRESERVE', 'ROTATE', 'BALANCED', 'ATTACK', 'ALL_OUT'"
NEW = "'DEFENSIVE', 'AGGRESSIVE', " + OLD


def constraint(modes: str) -> str:
    return (
        "(strategy IS NULL AND intent IS NOT NULL AND risk_focus IS NOT NULL) OR "
        f"(strategy IS NOT NULL AND strategy IN ({modes}) "
        "AND intent IS NULL AND risk_focus IS NULL)"
    )


def upgrade() -> None:
    with op.batch_alter_table("catalog_versions") as batch:
        batch.add_column(
            sa.Column("selection_ruleset", sa.String(40), nullable=False, server_default="open-v1")
        )
        batch.add_column(
            sa.Column("offer_allocation", sa.JSON(), nullable=False, server_default="[]")
        )
    with op.batch_alter_table("catalog_versions") as batch:
        batch.alter_column("selection_ruleset", server_default=None)
        batch.alter_column("offer_allocation", server_default=None)
    with op.batch_alter_table("decisions") as batch:
        batch.drop_constraint("decision_strategy_shape", type_="check")
        batch.create_check_constraint("decision_strategy_shape", constraint(NEW))


def downgrade() -> None:
    connection = op.get_bind()
    for table, condition in (
        ("matches", "ruleset IN ('v3.0', 'v3.1')"),
        ("drafts", "selection_ruleset IN ('tradeoffs-v1', 'simple-v1')"),
        ("catalog_versions", "selection_ruleset IN ('tradeoffs-v1', 'simple-v1')"),
        ("decisions", "strategy IN ('DEFENSIVE', 'AGGRESSIVE')"),
    ):
        if connection.scalar(sa.text(f"SELECT count(*) FROM {table} WHERE {condition}")):
            raise RuntimeError("Cannot downgrade while v3 matches, drafts or catalogs exist")
    with op.batch_alter_table("decisions") as batch:
        batch.drop_constraint("decision_strategy_shape", type_="check")
        batch.create_check_constraint("decision_strategy_shape", constraint(OLD))
    with op.batch_alter_table("catalog_versions") as batch:
        batch.drop_column("offer_allocation")
        batch.drop_column("selection_ruleset")
