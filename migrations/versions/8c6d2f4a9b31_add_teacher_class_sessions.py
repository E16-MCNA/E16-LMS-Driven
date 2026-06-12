"""add teacher class sessions

Revision ID: 8c6d2f4a9b31
Revises: 7f2a4c91d5b8
Create Date: 2026-06-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "8c6d2f4a9b31"
down_revision = "7f2a4c91d5b8"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "course_classes" not in tables:
        op.create_table(
            "course_classes",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("advisor_id", sa.String(length=36), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["advisor_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_course_classes_course_id", "course_classes", ["course_id"])
        op.create_index("ix_course_classes_advisor_id", "course_classes", ["advisor_id"])
        op.create_index("ix_course_classes_status", "course_classes", ["status"])
        op.create_index("idx_course_classes_course_status", "course_classes", ["course_id", "status"])

    class_columns = {col["name"] for col in sa.inspect(bind).get_columns("course_classes")} if "course_classes" in sa.inspect(bind).get_table_names() else set()
    if "advisor_id" not in class_columns:
        op.add_column("course_classes", sa.Column("advisor_id", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            "fk_course_classes_advisor_id_users",
            "course_classes",
            "users",
            ["advisor_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_course_classes_advisor_id", "course_classes", ["advisor_id"])

    if "class_sessions" not in tables:
        op.create_table(
            "class_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("class_id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("starts_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["course_classes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_class_sessions_class_id", "class_sessions", ["class_id"])
        op.create_index("ix_class_sessions_starts_at", "class_sessions", ["starts_at"])
        op.create_index("ix_class_sessions_status", "class_sessions", ["status"])
        op.create_index("idx_class_sessions_class_start", "class_sessions", ["class_id", "starts_at"])

    enrollment_columns = {col["name"] for col in inspector.get_columns("enrollments")}
    if "class_id" not in enrollment_columns:
        op.add_column("enrollments", sa.Column("class_id", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            "fk_enrollments_class_id_course_classes",
            "enrollments",
            "course_classes",
            ["class_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_enrollments_class_id", "enrollments", ["class_id"])

    if "class_session_lessons" not in tables:
        op.create_table(
            "class_session_lessons",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("lesson_id", sa.String(length=36), nullable=False),
            sa.Column("sequence_order", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["class_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "lesson_id", name="uq_class_session_lessons_session_lesson"),
        )
        op.create_index("ix_class_session_lessons_session_id", "class_session_lessons", ["session_id"])
        op.create_index("ix_class_session_lessons_lesson_id", "class_session_lessons", ["lesson_id"])
        op.create_index("idx_class_session_lessons_session", "class_session_lessons", ["session_id"])

    if "attendance_records" not in tables:
        op.create_table(
            "attendance_records",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("marked_at", sa.DateTime(), nullable=False),
            sa.Column("marked_by", sa.String(length=36), nullable=True),
            sa.ForeignKeyConstraint(["session_id"], ["class_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["marked_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "user_id", name="uq_attendance_records_session_user"),
        )
        op.create_index("ix_attendance_records_session_id", "attendance_records", ["session_id"])
        op.create_index("ix_attendance_records_user_id", "attendance_records", ["user_id"])
        op.create_index("ix_attendance_records_status", "attendance_records", ["status"])
        op.create_index("idx_attendance_records_session_status", "attendance_records", ["session_id", "status"])

    forum_columns = {col["name"] for col in inspector.get_columns("forum_threads")}
    if "class_id" not in forum_columns:
        op.add_column("forum_threads", sa.Column("class_id", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            "fk_forum_threads_class_id_course_classes",
            "forum_threads",
            "course_classes",
            ["class_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index("ix_forum_threads_class_id", "forum_threads", ["class_id"])


def downgrade():
    with op.batch_alter_table("forum_threads", schema=None) as batch_op:
        batch_op.drop_index("ix_forum_threads_class_id")
        batch_op.drop_constraint("fk_forum_threads_class_id_course_classes", type_="foreignkey")
        batch_op.drop_column("class_id")

    with op.batch_alter_table("enrollments", schema=None) as batch_op:
        batch_op.drop_index("ix_enrollments_class_id")
        batch_op.drop_constraint("fk_enrollments_class_id_course_classes", type_="foreignkey")
        batch_op.drop_column("class_id")

    for table_name in [
        "attendance_records",
        "class_session_lessons",
        "class_sessions",
        "course_classes",
    ]:
        op.drop_table(table_name)
