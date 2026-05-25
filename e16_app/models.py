# -*- coding: utf-8 -*-
import uuid
from datetime import datetime, timezone

from flask_login import UserMixin

from .extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


# --- Role & Status Constants ---
VALID_ROLES = {"admin", "teacher", "student", "hoc_vu", "le_tan", "ke_toan"}

COURSE_STATUSES = {
    "draft", "pending_review", "approved", "published",
    "running", "closed", "archived", "suspended", "rejected",
}

COURSE_TRANSITIONS = {
    "draft":          ["pending_review"],
    "pending_review": ["approved", "rejected"],
    "rejected":       ["draft"],
    "approved":       ["published"],
    "published":      ["running", "suspended"],
    "running":        ["closed", "suspended"],
    "suspended":      ["running", "published"],
    "closed":         ["archived"],
    "archived":       [],
}


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.Index("idx_users_role_created", "role", "created_at"),
    )
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    login_count = db.Column(db.Integer, default=0, nullable=False)
    reset_token = db.Column(db.String(100), nullable=True, unique=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    # --- New: Force password change & account provenance ---
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    temp_password_hash = db.Column(db.String(255), nullable=True)


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), default="")
    icon = db.Column(db.String(50), default="📚")
    sort_order = db.Column(db.Integer, default=0)


class Course(db.Model):
    __tablename__ = "courses"
    __table_args__ = (
        db.Index('idx_courses_status_deleted', 'status', 'is_deleted'),
    )
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    title = db.Column(db.String(255), nullable=False)
    short_description = db.Column(db.String(500), default="", nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    cover_image_url = db.Column(db.String(500), default="", nullable=False)
    total_lessons = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False, index=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    category_id = db.Column(db.String(36), db.ForeignKey("categories.id"), nullable=True, index=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    rejection_note = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    price = db.Column(db.Integer, default=250000, nullable=False)
    tags = db.Column(db.String(500), default="", nullable=False)  # Comma-separated: "Python,Data,AI"
    level = db.Column(db.String(20), default="", nullable=False)  # Beginner, Intermediate, Advanced
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    # --- New: Full lifecycle metadata ---
    reviewed_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    enrollment_deadline = db.Column(db.DateTime, nullable=True)
    max_students = db.Column(db.Integer, nullable=True)  # null = unlimited


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    actor_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(36))
    detail = db.Column(db.Text)  # JSON string
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=_utcnow)

    @property
    def metadata_json(self):
        import json
        if not self.detail:
            return {}
        try:
            return json.loads(self.detail)
        except Exception:
            return {}


class Lesson(db.Model):
    __tablename__ = "lessons"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    video_url = db.Column(db.String(500), default="", nullable=False)
    document_url = db.Column(db.String(500), default="", nullable=False)
    sequence_order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (
        db.UniqueConstraint("user_id", "course_id", name="uq_enrollments_user_course"),
        db.Index("idx_enrollments_status_course", "status", "course_id"),
        db.Index("idx_enrollments_user_status", "user_id", "status"),
    )
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    enrolled_at = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)
    status = db.Column(db.String(20), default="active", nullable=False, index=True)  # active, dropped, completed

    # Ledger fields for payment accounting
    amount_paid = db.Column(db.Integer, nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)
    tx_code = db.Column(db.String(100), nullable=True)
    approved_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_reason = db.Column(db.Text, nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)

    # ORM relationships for joinedload
    course = db.relationship("Course", lazy="select")
    user = db.relationship("User", lazy="select", foreign_keys=[user_id])


class LearningLog(db.Model):
    __tablename__ = "learning_logs"
    __table_args__ = (
        db.Index('idx_learning_logs_user_action', 'user_id', 'action_type'),
    )
    log_id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id = db.Column(db.String(36), db.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = db.Column(db.String(20), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)


# --- Quiz System Models ---

class Quiz(db.Model):
    __tablename__ = "quizzes"
    __table_args__ = (
        db.Index("idx_quizzes_course_published_due", "course_id", "is_published", "due_date"),
    )
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    pass_score = db.Column(db.Integer, default=80)
    max_attempts = db.Column(db.Integer, default=3)
    time_limit = db.Column(db.Integer, nullable=True)  # Giới hạn thời gian thi (phút)
    random_question_count = db.Column(db.Integer, default=0) # Ngân hàng câu hỏi: số câu sẽ lấy ngẫu nhiên
    due_date = db.Column(db.DateTime, nullable=True)
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_utcnow)


# --- Sprint 3 Models ---

class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False)  # new_assignment, graded, announcement, forum_reply
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=_utcnow)


class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_utcnow)


class ForumThread(db.Model):
    __tablename__ = "forum_threads"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=_utcnow)


class ForumReply(db.Model):
    __tablename__ = "forum_replies"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    thread_id = db.Column(db.String(36), db.ForeignKey("forum_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=_utcnow)


class Certificate(db.Model):
    __tablename__ = "certificates"
    __table_args__ = (
        db.UniqueConstraint("user_id", "course_id", name="uq_certificates_user_course"),
    )
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    cert_code = db.Column(db.String(100), unique=True, default=new_uuid)
    issued_at = db.Column(db.DateTime, default=_utcnow)


class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    quiz_id = db.Column(db.String(36), db.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    q_type = db.Column(db.String(20), default="mcq")  # mcq, true_false
    sequence_order = db.Column(db.Integer, default=0)


class Choice(db.Model):
    __tablename__ = "choices"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    quiz_id = db.Column(db.String(36), db.ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score = db.Column(db.Integer, index=True)
    passed = db.Column(db.Boolean, index=True)
    attempted_at = db.Column(db.DateTime, default=_utcnow, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)


class QuizAnswer(db.Model):
    __tablename__ = "quiz_answers"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    attempt_id = db.Column(db.String(36), db.ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    choice_id = db.Column(db.String(36), db.ForeignKey("choices.id", ondelete="CASCADE"), nullable=True)
    text_answer = db.Column(db.Text, nullable=True)


# --- Assignment Models ---

class Assignment(db.Model):
    __tablename__ = "assignments"
    __table_args__ = (
        db.Index("idx_assignments_course_deadline", "course_id", "deadline"),
    )
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.DateTime)
    allow_file = db.Column(db.Boolean, default=True)
    allow_text = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utcnow)


class Submission(db.Model):
    __tablename__ = "submissions"
    __table_args__ = (
        db.UniqueConstraint("user_id", "assignment_id", name="uq_submissions_user_assignment"),
        db.Index("idx_submissions_assignment_status", "assignment_id", "status"),
        db.Index("idx_submissions_user_assignment_status", "user_id", "assignment_id", "status"),
    )
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    assignment_id = db.Column(db.String(36), db.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    text_content = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    submitted_at = db.Column(db.DateTime, default=_utcnow)
    status = db.Column(db.String(20), default="pending")  # pending, graded, revision_needed
    score = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    graded_at = db.Column(db.DateTime, nullable=True)
    graded_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ContentReport(db.Model):
    __tablename__ = "content_reports"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    reporter_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type = db.Column(db.String(20), nullable=False)  # "thread" or "reply"
    target_id = db.Column(db.String(36), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    detail = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)  # pending, resolved, dismissed
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action_taken = db.Column(db.String(50), nullable=True)  # "hidden", "dismissed"


class BackgroundJob(db.Model):
    __tablename__ = "background_jobs"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    task_name = db.Column(db.String(100), nullable=False)  # e.g., "send_announcement_email", "export_large_data"
    payload = db.Column(db.Text, nullable=False)  # JSON-encoded payload
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)  # pending, running, completed, failed
    attempts = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=3, nullable=False)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)


class PaymentTransaction(db.Model):
    __tablename__ = "payment_transactions"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    enrollment_id = db.Column(db.String(36), db.ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    tx_code = db.Column(db.String(100), unique=False, index=True, nullable=True)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    processed_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    enrollment = db.relationship("Enrollment", lazy="select", backref=db.backref("transactions", cascade="all, delete-orphan"))
    user = db.relationship("User", lazy="select", foreign_keys=[user_id])
    course = db.relationship("Course", lazy="select", foreign_keys=[course_id])
    processor = db.relationship("User", lazy="select", foreign_keys=[processed_by])
