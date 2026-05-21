"""Add role system, course lifecycle, and account provenance columns

Revision ID: a1b2c3d4e5f6
Revises: f2c1a9d8e3b4
Create Date: 2026-05-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f2c1a9d8e3b4"
branch_labels = None
depends_on = None


def upgrade():
    # --- Users table: force-change-password + provenance ---
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.add_column("users", sa.Column("created_by", sa.String(length=36), nullable=True))
    op.add_column("users", sa.Column("temp_password_hash", sa.String(length=255), nullable=True))
    op.create_index("idx_users_created_by", "users", ["created_by"])
    op.create_foreign_key(
        "fk_users_created_by_users",
        "users",
        "users",
        ["created_by"],
        ["id"],
    )

    # --- Courses table: full lifecycle metadata ---
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("reviewed_by", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("reviewed_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("review_note", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("starts_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ends_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("enrollment_deadline", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("max_students", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_courses_reviewed_by_users",
            "users",
            ["reviewed_by"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.drop_constraint("fk_courses_reviewed_by_users", type_="foreignkey")
        batch_op.drop_column("max_students")
        batch_op.drop_column("enrollment_deadline")
        batch_op.drop_column("ends_at")
        batch_op.drop_column("starts_at")
        batch_op.drop_column("review_note")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("fk_users_created_by_users", type_="foreignkey")
        batch_op.drop_index("idx_users_created_by")
        batch_op.drop_column("temp_password_hash")
        batch_op.drop_column("created_by")
        batch_op.drop_column("must_change_password")
