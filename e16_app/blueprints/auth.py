from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import Course, Enrollment, Lesson, User
from ..services import recalc_total_lessons

bp = Blueprint("auth", __name__)


@bp.route("/")
def home():
    if not g.user:
        return redirect(url_for("auth.login"))
    if g.user.role == "student":
        return redirect(url_for("student.dashboard"))
    if g.user.role == "teacher":
        return redirect(url_for("teacher.manage_courses"))
    return redirect(url_for("analytics.dashboard"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")
        if role not in {"student", "teacher", "admin"}:
            flash("Role không hợp lệ.", "error")
            return redirect(url_for("auth.register"))
        if not email or not password:
            flash("Email và mật khẩu là bắt buộc.", "error")
            return redirect(url_for("auth.register"))
        if db.session.query(User).filter(User.email == email).first():
            flash("Email đã tồn tại.", "error")
            return redirect(url_for("auth.register"))
        user = User(email=email, password_hash=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.commit()
        flash("Đăng ký thành công. Mời đăng nhập.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html", user=g.user)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.session.query(User).filter(User.email == email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Thông tin đăng nhập không đúng.", "error")
            return redirect(url_for("auth.login"))
        user.last_login = datetime.utcnow()
        user.login_count = (user.login_count or 0) + 1
        db.session.commit()
        session["user_id"] = user.id
        return redirect(url_for("auth.home"))
    return render_template("login.html", user=g.user)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/seed")
def seed():
    if db.session.query(User).count() > 0:
        return "Seed skipped: database already has data."
    student = User(email="student@e16.local", password_hash=generate_password_hash("123456"), role="student")
    teacher = User(email="teacher@e16.local", password_hash=generate_password_hash("123456"), role="teacher")
    admin = User(email="admin@e16.local", password_hash=generate_password_hash("123456"), role="admin")
    db.session.add_all([student, teacher, admin])
    db.session.commit()

    course = Course(
        title="Data-Driven Product Fundamentals",
        description="Khoá học demo cho E16 MVP.",
        cover_image_url="https://images.unsplash.com/photo-1516321318423-f06f85e504b3",
        teacher_id=teacher.id,
    )
    db.session.add(course)
    db.session.commit()

    lessons = [
        Lesson(
            course_id=course.id,
            title="Lesson 1 - Product Metrics",
            video_url="https://www.youtube.com/embed/dQw4w9WgXcQ",
            document_url="https://example.com/doc-1",
            sequence_order=1,
        ),
        Lesson(
            course_id=course.id,
            title="Lesson 2 - Retention",
            video_url="https://www.youtube.com/embed/oHg5SJYRHA0",
            document_url="https://example.com/doc-2",
            sequence_order=2,
        ),
        Lesson(
            course_id=course.id,
            title="Lesson 3 - Funnel",
            video_url="https://www.youtube.com/embed/2Z4m4lnjxkY",
            document_url="https://example.com/doc-3",
            sequence_order=3,
        ),
    ]
    db.session.add_all(lessons)
    db.session.commit()
    recalc_total_lessons(course.id)

    db.session.add(Enrollment(user_id=student.id, course_id=course.id, status="in_progress"))
    db.session.commit()
    return "Seeded demo data. Accounts: student/teacher/admin with password 123456."
