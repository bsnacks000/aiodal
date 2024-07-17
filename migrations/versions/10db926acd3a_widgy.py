"""widgy

Revision ID: 10db926acd3a
Revises: b8333803ffda
Create Date: 2024-07-17 06:51:13.282029

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "10db926acd3a"
down_revision = "b8333803ffda"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create schema w")
    op.create_table(
        "widgy",
        sa.Column(
            "id", sa.UUID, primary_key=True, server_default=sa.func.gen_random_uuid()
        ),
        sa.Column("thing", sa.String(64)),
        sa.Column("n", sa.Numeric),
        schema="w",
    )


def downgrade() -> None: ...
