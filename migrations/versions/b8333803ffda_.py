"""empty message

Revision ID: b8333803ffda
Revises: 74d1ce0ca025
Create Date: 2024-01-25 14:26:52.488244

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8333803ffda"
down_revision = "74d1ce0ca025"
branch_labels = None
depends_on = None

from sqlalchemy.dialects.postgresql import UUID

# simulate stuff added for aiodal.web versioning


def upgrade() -> None:
    op.add_column(
        "book",
        sa.Column("etag_version", UUID, server_default=sa.text("gen_random_uuid()")),
    )
    op.add_column(
        "author",
        sa.Column("etag_version", UUID, server_default=sa.text("gen_random_uuid()")),
    )
    op.add_column("book", sa.Column("deleted", sa.Boolean, server_default="f"))
    op.add_column("author", sa.Column("deleted", sa.Boolean, server_default="f"))


def downgrade() -> None:
    pass
