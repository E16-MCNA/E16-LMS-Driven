"""merge two heads

Revision ID: 164371be035c
Revises: 41db866ec8eb, a1b2c3d4e5f6
Create Date: 2026-05-21 17:31:48.859976

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '164371be035c'
down_revision = ('41db866ec8eb', 'a1b2c3d4e5f6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
