"""initial

Revision ID: 74d1ce0ca025
Revises: 
Create Date: 2023-02-15 08:31:37.385944

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '74d1ce0ca025'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('author', 
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(64), nullable=False))

    op.create_table('book', 
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True), 
        sa.Column('author_id',sa.Integer,  sa.ForeignKey('author.id',ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(64)), 
        sa.Column('catalog', sa.String(64)),
        sa.UniqueConstraint('catalog', name='uc__book'))


def downgrade() -> None:
    op.drop_table('author')
    op.drop_table('book')
