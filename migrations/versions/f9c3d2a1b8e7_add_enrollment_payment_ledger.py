"""Add enrollment payment ledger columns

Revision ID: f9c3d2a1b8e7
Revises: 164371be035c
Create Date: 2026-05-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f9c3d2a1b8e7"
down_revision = "164371be035c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("enrollments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("amount_paid", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("payment_method", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("tx_code", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("approved_by", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("rejected_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("refunded_at", sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            "fk_enrollments_approved_by_users",
            "users",
            ["approved_by"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("enrollments", schema=None) as batch_op:
        batch_op.drop_constraint("fk_enrollments_approved_by_users", type_="foreignkey")
        batch_op.drop_column("refunded_at")
        batch_op.drop_column("rejected_reason")
        batch_op.drop_column("approved_at")
        batch_op.drop_column("approved_by")
        batch_op.drop_column("tx_code")
        batch_op.drop_column("payment_method")
        batch_op.drop_column("amount_paid")
