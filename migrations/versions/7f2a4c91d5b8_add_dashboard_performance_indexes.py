"""add dashboard performance indexes

Revision ID: 7f2a4c91d5b8
Revises: 3e419f6477f1
Create Date: 2026-05-24 03:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f2a4c91d5b8"
down_revision = "3e419f6477f1"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def create_index_once(table_name, index_name, columns):
        existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
        if index_name not in existing:
            op.create_index(index_name, table_name, columns, unique=False)

    create_index_once("users", "idx_users_role_created", ["role", "created_at"])
    create_index_once("enrollments", "idx_enrollments_status_course", ["status", "course_id"])
    create_index_once("enrollments", "idx_enrollments_user_status", ["user_id", "status"])
    create_index_once("quizzes", "idx_quizzes_course_published_due", ["course_id", "is_published", "due_date"])
    create_index_once("assignments", "idx_assignments_course_deadline", ["course_id", "deadline"])
    create_index_once("submissions", "idx_submissions_assignment_status", ["assignment_id", "status"])
    create_index_once("submissions", "idx_submissions_user_assignment_status", ["user_id", "assignment_id", "status"])


def downgrade():
    with op.batch_alter_table("submissions", schema=None) as batch_op:
        batch_op.drop_index("idx_submissions_user_assignment_status")
        batch_op.drop_index("idx_submissions_assignment_status")

    with op.batch_alter_table("assignments", schema=None) as batch_op:
        batch_op.drop_index("idx_assignments_course_deadline")

    with op.batch_alter_table("quizzes", schema=None) as batch_op:
        batch_op.drop_index("idx_quizzes_course_published_due")

    with op.batch_alter_table("enrollments", schema=None) as batch_op:
        batch_op.drop_index("idx_enrollments_user_status")
        batch_op.drop_index("idx_enrollments_status_course")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("idx_users_role_created")
