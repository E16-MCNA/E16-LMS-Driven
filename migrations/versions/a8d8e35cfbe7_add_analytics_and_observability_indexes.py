"""add analytics and observability indexes

Revision ID: a8d8e35cfbe7
Revises: 90f827b5d6e3
Create Date: 2026-05-17 22:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8d8e35cfbe7'
down_revision = '90f827b5d6e3'
branch_labels = None
depends_on = None


def upgrade():
    # Add new index fields to optimize analytics queries
    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_enrollments_enrolled_at'), ['enrolled_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_enrollments_status'), ['status'], unique=False)

    with op.batch_alter_table('learning_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_learning_logs_action_type'), ['action_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_learning_logs_timestamp'), ['timestamp'], unique=False)

    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_quiz_attempts_score'), ['score'], unique=False)
        batch_op.create_index(batch_op.f('ix_quiz_attempts_passed'), ['passed'], unique=False)
        batch_op.create_index(batch_op.f('ix_quiz_attempts_attempted_at'), ['attempted_at'], unique=False)


def downgrade():
    with op.batch_alter_table('quiz_attempts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_quiz_attempts_attempted_at'))
        batch_op.drop_index(batch_op.f('ix_quiz_attempts_passed'))
        batch_op.drop_index(batch_op.f('ix_quiz_attempts_score'))

    with op.batch_alter_table('learning_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_learning_logs_timestamp'))
        batch_op.drop_index(batch_op.f('ix_learning_logs_action_type'))

    with op.batch_alter_table('enrollments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_enrollments_status'))
        batch_op.drop_index(batch_op.f('ix_enrollments_enrolled_at'))
