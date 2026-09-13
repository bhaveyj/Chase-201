"""Add v2 profiles and one-axis decisions without changing saved match rulesets."""

import hashlib

import sqlalchemy as sa
from alembic import op

revision = "e20a91d8f672"
down_revision = "c95af1b9cdb8"
branch_labels = None
depends_on = None
ATTRIBUTES = (
    "batting_control",
    "batting_rotation",
    "batting_power",
    "bowling_control",
    "bowling_threat",
)


def upgrade():
    for name in ATTRIBUTES:
        op.add_column("simulation_profiles", sa.Column(name, sa.Float(), nullable=True))
    op.add_column("simulation_profiles", sa.Column("bowling_style", sa.String(10), nullable=True))
    profiles = sa.table(
        "simulation_profiles",
        sa.column("player_id"),
        sa.column("batting"),
        sa.column("bowling"),
        *[sa.column(name) for name in (*ATTRIBUTES, "bowling_style")],
    )
    connection = op.get_bind()
    # Freeze the backfill here so future importer changes cannot rewrite migration history.
    for row in connection.execute(
        sa.select(profiles.c.player_id, profiles.c.batting, profiles.c.bowling)
    ).mappings():
        digest = hashlib.sha256(row["player_id"].encode()).digest()
        values = {
            name: round(
                max(1, min(100, row["batting" if i < 3 else "bowling"] + digest[i] % 17 - 8)), 2
            )
            for i, name in enumerate(ATTRIBUTES)
        }
        values["bowling_style"] = "PACE" if digest[5] % 2 == 0 else "SPIN"
        connection.execute(
            profiles.update().where(profiles.c.player_id == row["player_id"]).values(**values)
        )
    with op.batch_alter_table("simulation_profiles") as batch:
        for name in ATTRIBUTES:
            batch.alter_column(name, existing_type=sa.Float(), nullable=False)
            batch.create_check_constraint(f"profile_{name}", f"{name} BETWEEN 1 AND 100")
        batch.alter_column("bowling_style", existing_type=sa.String(10), nullable=False)
        batch.create_check_constraint("profile_bowling_style", "bowling_style IN ('PACE', 'SPIN')")
    with op.batch_alter_table("decisions") as batch:
        batch.alter_column("intent", existing_type=sa.String(20), nullable=True)
        batch.alter_column("risk_focus", existing_type=sa.String(30), nullable=True)
        batch.add_column(sa.Column("strategy", sa.String(20), nullable=True))
        batch.add_column(sa.Column("context_summary", sa.JSON(), nullable=True))
        batch.create_check_constraint(
            "decision_strategy_shape",
            "(strategy IS NULL AND intent IS NOT NULL AND risk_focus IS NOT NULL) OR "
            "(strategy IS NOT NULL AND strategy IN ('PRESERVE', 'ROTATE', 'BALANCED', 'ATTACK', 'ALL_OUT') "
            "AND intent IS NULL AND risk_focus IS NULL)",
        )


def downgrade():
    # Downgrading cannot represent live v2 games. Refuse rather than corrupt them.
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT COUNT(*) FROM matches WHERE ruleset <> 'v1.0'")).scalar():
        raise RuntimeError(
            "Cannot downgrade while v2 matches exist; restore the pre-upgrade backup"
        )
    with op.batch_alter_table("decisions") as batch:
        batch.drop_constraint("decision_strategy_shape", type_="check")
        batch.drop_column("context_summary")
        batch.drop_column("strategy")
        batch.alter_column("intent", existing_type=sa.String(20), nullable=False)
        batch.alter_column("risk_focus", existing_type=sa.String(30), nullable=False)
    with op.batch_alter_table("simulation_profiles") as batch:
        for name in (*ATTRIBUTES, "bowling_style"):
            batch.drop_constraint(f"profile_{name}", type_="check")
            batch.drop_column(name)
