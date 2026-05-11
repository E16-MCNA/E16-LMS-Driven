import uuid
from datetime import datetime

from flask_login import UserMixin

from .extensions import db


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    login_count = db.Column(db.Integer, default=0, nullable=False)
    reset_token = db.Column(db.String(100), nullable=True, unique=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)


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
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    title = db.Column(db.String(255), nullable=False)
    short_description = db.Column(db.String(500), default="", nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    cover_image_url = db.Column(db.String(500), default="", nullable=False)
    total_lessons = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False)  # draft, pending_review, published, rejected
    category_id = db.Column(db.String(36), db.ForeignKey("categories.id"), nullable=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    rejection_note = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    actor_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(36))
    detail = db.Column(db.Text)  # JSON string
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Lesson(db.Model):
    __tablename__ = "lessons"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    video_url = db.Column(db.String(500), default="", nullable=False)
    document_url = db.Column(db.String(500), default="", nullable=False)
    sequence_order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)  # active, dropped, completed


class LearningLog(db.Model):
    __tablename__ = "learning_logs"
    log_id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    lesson_id = db.Column(db.String(36), db.ForeignKey("lessons.id"), nullable=False)
    action_type = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# --- Quiz System Models ---

class Quiz(db.Model):
    __tablename__ = "quizzes"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    pass_score = db.Column(db.Integer, default=80)
    max_attempts = db.Column(db.Integer, default=3)
    due_date = db.Column(db.DateTime, nullable=True)
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)





# --- Sprint 3 Models ---

class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # new_assignment, graded, announcement, forum_reply
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ForumThread(db.Model):
    __tablename__ = "forum_threads"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ForumReply(db.Model):
    __tablename__ = "forum_replies"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    thread_id = db.Column(db.String(36), db.ForeignKey("forum_threads.id"), nullable=False)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Certificate(db.Model):
    __tablename__ = "certificates"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    cert_code = db.Column(db.String(100), unique=True, default=new_uuid)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)


class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    quiz_id = db.Column(db.String(36), db.ForeignKey("quizzes.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    q_type = db.Column(db.String(20), default="mcq")  # mcq, true_false
    sequence_order = db.Column(db.Integer, default=0)


class Choice(db.Model):
    __tablename__ = "choices"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    quiz_id = db.Column(db.String(36), db.ForeignKey("quizzes.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Integer)
    passed = db.Column(db.Boolean)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)


class QuizAnswer(db.Model):
    __tablename__ = "quiz_answers"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    attempt_id = db.Column(db.String(36), db.ForeignKey("quiz_attempts.id"), nullable=False)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id"), nullable=False)
    choice_id = db.Column(db.String(36), db.ForeignKey("choices.id"), nullable=False)


# --- Assignment Models ---

class Assignment(db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    course_id = db.Column(db.String(36), db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    deadline = db.Column(db.DateTime)
    allow_file = db.Column(db.Boolean, default=True)
    allow_text = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    assignment_id = db.Column(db.String(36), db.ForeignKey("assignments.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    text_content = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending")  # pending, graded, revision_needed
    score = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    graded_at = db.Column(db.DateTime, nullable=True)
    graded_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
