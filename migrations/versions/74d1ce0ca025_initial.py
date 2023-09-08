"""initial

Revision ID: 74d1ce0ca025
Revises: 
Create Date: 2023-02-15 08:31:37.385944

"""
from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "74d1ce0ca025"
down_revision = None
branch_labels = None
depends_on = None


# classic rel db example nonsense... this is for basic testing
def upgrade() -> None:
    op.execute("create schema testschema1")
    op.execute("create schema testschema2")

    op.create_table(
        "author",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False),
    )

    op.create_table(
        "book",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "author_id",
            sa.Integer,
            sa.ForeignKey("author.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(64)),
        sa.Column("catalog", sa.String(64)),
        sa.Column("extra", JSONB, server_default="{}"),
        sa.UniqueConstraint("catalog", name="uc__book"),
    )

    op.create_table(
        "table1",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("column1", sa.String(64)),
        sa.UniqueConstraint("column1", name="uc__table1"),
        schema="testschema1",
    )

    op.create_table(
        "table2",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "table1_id",
            sa.Integer,
            sa.ForeignKey("testschema1.table1.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("column2", sa.String(64)),
        sa.UniqueConstraint("column2", name="uc__table2"),
        schema="testschema1",
    )

    op.create_table(
        "table1",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("column3", sa.String(64)),
        sa.UniqueConstraint("column3", name="uc__testschema2table1"),
        schema="testschema2",
    )


def downgrade() -> None:
    op.drop_table("author")
    op.drop_table("book")
    op.drop_table("testschema1.table1")
    op.drop_table("testschema1.table2")
    op.drop_table("testschema2.table1")
    op.execute("drop schema testschema1")
    op.execute("drop schema testschema2")
