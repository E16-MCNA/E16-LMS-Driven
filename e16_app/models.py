import uuid
from datetime import datetime

from .extensions import db


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    login_count = db.Column(db.Integer, default=0, nullable=False)


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    cover_image_url = db.Column(db.String(500), default="", nullable=False)
    total_lessons = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    teacher_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)


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
    status = db.Column(db.String(20), default="in_progress", nullable=False)


class LearningLog(db.Model):
    __tablename__ = "learning_logs"
    log_id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    lesson_id = db.Column(db.String(36), db.ForeignKey("lessons.id"), nullable=False)
    action_type = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
