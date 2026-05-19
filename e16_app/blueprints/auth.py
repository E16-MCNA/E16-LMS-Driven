# -*- coding: utf-8 -*-
import os
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, oauth, limiter
from ..models import Course, Enrollment, LearningLog, Lesson, User
from ..services.course import recalc_total_lessons
from ..services.logging import logger

bp = Blueprint("auth", __name__)


def _utcnow():
    return datetime.now(timezone.utc)


@bp.route("/login/<name>")
def oauth_login(name):
    client = oauth.create_client(name)
    if not client:
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.oauth_authorize", name=name, _external=True)
    return client.authorize_redirect(redirect_uri)


@bp.route("/authorize/<name>")
def oauth_authorize(name):
    client = oauth.create_client(name)
    if not client:
        return redirect(url_for("auth.login"))
    
    try:
        token = client.authorize_access_token()
    except Exception as e:
        current_app.logger.error(f"OAuth error: {str(e)}")
        flash("Đăng nhập thất bại. Vui lòng thử lại.", "error")
        return redirect(url_for("auth.login"))

    user_info = token.get("userinfo")
    if not user_info:
        # Fallback for non-OIDC or if userinfo not in token
        user_info = client.get("userinfo").json()
        
    if not user_info or not user_info.get("email"):
        flash("Không thể lấy thông tin email từ nhà cung cấp.", "error")
        return redirect(url_for("auth.login"))

    email = user_info["email"].lower()
    user = db.session.query(User).filter(User.email == email).first()

    if not user:
        # Tự động tạo tài khoản nếu chưa có
        user = User(
            email=email,
            password_hash=generate_password_hash(secrets.token_urlsafe(16)),
            role="student",
        )
        db.session.add(user)
        db.session.commit()

    user.last_login = _utcnow()
    user.login_count = (user.login_count or 0) + 1
    db.session.commit()

    login_user(user)
    from ..services.audit import log_action
    log_action("login_success", "User", user.id, {"email": email, "method": f"oauth_{name}"})
    logger.log(f"login_oauth_{name}", user_id=user.id, user_email=user.email, metadata={"method": name})
    flash(f"Chào mừng {email}!", "success")
    return redirect(url_for("auth.home"))


@bp.route("/")
def home():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.role == "student":
        return redirect(url_for("student.dashboard"))
    if current_user.role == "teacher":
        return redirect(url_for("teacher.dashboard"))
    return redirect(url_for("analytics.dashboard"))


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("15 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "student")
        # Security: chỉ cho phép student hoặc teacher tự đăng ký
        if role not in {"student", "teacher"}:
            role = "student"
        if len(password) < 8:
            flash("Mật khẩu phải có ít nhất 8 ký tự.", "error")
            return redirect(url_for("auth.register"))
        confirm_password = request.form.get("confirm_password", "")
        if password != confirm_password:
            flash("Mật khẩu và xác nhận mật khẩu không khớp.", "error")
            return redirect(url_for("auth.register"))
        if not email or not password:
            flash("Email và mật khẩu là bắt buộc.", "error")
            return redirect(url_for("auth.register"))
        if db.session.query(User).filter(User.email == email).first():
            flash("Email đã tồn tại.", "error")
            return redirect(url_for("auth.register"))
        user = User(email=email, password_hash=generate_password_hash(password), role=role, phone=phone)
        db.session.add(user)
        db.session.commit()
        from ..services.audit import log_action
        log_action("user_registered", "User", user.id, {"email": email, "role": role})
        logger.log("register", user_id=user.id, user_email=user.email, metadata={"role": role})
        flash("Đăng ký thành công. Mời đăng nhập.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("15 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.session.query(User).filter(User.email == email).first()
        if not user or not check_password_hash(user.password_hash, password):
            from ..services.audit import log_action
            log_action("login_failed", "User", user.id if user else None, {"email": email})
            flash("Email hoặc mật khẩu không chính xác.", "error")
            return redirect(url_for("auth.login"))
        if not user.is_active:
            from ..services.audit import log_action
            log_action("login_failed_inactive", "User", user.id, {"email": email})
            flash("Tài khoản của bạn đã bị vô hiệu hóa. Vui lòng liên hệ Admin.", "error")
            return redirect(url_for("auth.login"))
        user.last_login = _utcnow()
        user.login_count = (user.login_count or 0) + 1
        db.session.commit()
        login_user(user)
        from ..services.audit import log_action
        log_action("login_success", "User", user.id, {"email": email, "method": "email"})
        logger.log("login", user_id=user.id, user_email=user.email, metadata={"method": "email"})
        return redirect(url_for("auth.home"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    if current_user.is_authenticated:
        logger.log("logout", user_id=current_user.id, user_email=current_user.email)
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = db.session.query(User).filter(User.email == email).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = _utcnow() + timedelta(hours=1)
            db.session.commit()
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            # Gửi email thật nếu SMTP đã cấu hình
            _send_reset_email(email, reset_url)
        # Security: luôn trả về thông báo chung để chống email enumeration
        flash("Nếu email tồn tại trong hệ thống, một liên kết đặt lại mật khẩu sẽ được gửi.", "info")
        return redirect(url_for("auth.login"))
    return render_template("forgot_password.html", user=None)


def _send_reset_email(email, reset_url):
    """Gửi email reset password. Fallback sang logger nếu SMTP chưa cấu hình."""
    try:
        if current_app.config.get("MAIL_USERNAME"):
            from ..services.mail import send_email
            send_email(
                to=email,
                subject="E16 LMS — Đặt lại mật khẩu",
                template_name="reset_password",
                reset_url=reset_url,
                email=email,
            )
            current_app.logger.info(f"Password reset email sent to {email}")
        else:
            # SMTP chưa cấu hình — chỉ log trong debug
            if current_app.debug:
                current_app.logger.debug(f"Password reset link for {email}: {reset_url}")
    except Exception as e:
        current_app.logger.error(f"Failed to send reset email to {email}: {e}")
        if current_app.debug:
            current_app.logger.debug(f"Password reset link for {email}: {reset_url}")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = db.session.query(User).filter(User.reset_token == token, User.reset_token_expiry > _utcnow()).first()
    if not user:
        flash("Liên kết không hợp lệ hoặc đã hết hạn.", "error")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        password = request.form.get("password", "")
        if not password or len(password) < 8:
            flash("Mật khẩu phải có ít nhất 8 ký tự.", "error")
            return redirect(url_for("auth.reset_password", token=token))
        user.password_hash = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash("Mật khẩu đã được cập nhật. Vui lòng đăng nhập lại.", "success")
        return redirect(url_for("auth.login"))
    return render_template("reset_password.html", token=token, user=None)



def _run_seed(seed_password):
    """Core seed logic — shared between HTTP route and CLI command."""
    import random
    from ..models import Category
    
    db.create_all() 
    
    cats_data = [
        ("Technology", "tech", "💻"),
        ("Design", "design", "🎨"),
        ("Business", "business", "💼"),
        ("Marketing", "marketing", "🚀")
    ]
    categories = {}
    for name, slug, icon in cats_data:
        cat = db.session.query(Category).filter_by(slug=slug).first()
        if not cat:
            cat = Category(name=name, slug=slug, icon=icon)
            db.session.add(cat)
            db.session.commit()
        categories[slug] = cat

    # 1. Create Core Test Users (User Request)
    core_users = [
        ("admin@e16.local", "admine16", "admin"),
        ("teacher@e16.local", "teachere16", "teacher"),
        ("student@e16.local", "studente16", "student")
    ]
    
    teacher = None
    for email, pwd, role in core_users:
        u = db.session.query(User).filter_by(email=email).first()
        if not u:
            u = User(email=email, password_hash=generate_password_hash(pwd), role=role)
            db.session.add(u)
        else:
            # Force the correct role if user already exists
            u.role = role
        db.session.commit()
        if role == "teacher":
            teacher = u

    # 2. Extra students for variety
    for i in range(1, 6):
        email = f"student{i}@e16.local"
        if not db.session.query(User).filter_by(email=email).first():
            db.session.add(User(email=email, password_hash=generate_password_hash(seed_password), role="student"))
    db.session.commit()

    course_data = [
        ("AI for Beginners", "Làm quen với AI", "Khám phá thế giới trí tuệ nhân tạo từ con số 0.", "https://images.unsplash.com/photo-1677442136019-21780ecad995", "tech"),
        ("UI/UX Design Essentials", "Thiết kế đỉnh cao", "Thiết kế giao diện người dùng đỉnh cao với Figma.", "https://images.unsplash.com/photo-1586717791821-3f44a563dc4c", "design"),
        ("Financial Freedom", "Tự do tài chính", "Quản lý tài chính cá nhân hiệu quả và bền vững.", "https://images.unsplash.com/photo-1554224155-6726b3ff858f", "business"),
        ("Digital Marketing 101", "Marketing số cơ bản", "Bùng nổ doanh số với Marketing số đa kênh.", "https://images.unsplash.com/photo-1460925895917-afdab827c52f", "marketing")
    ]
    
    for title, short_desc, desc, img, cat_slug in course_data:
        if not db.session.query(Course).filter(Course.title == title).first():
            c = Course(
                title=title, 
                short_description=short_desc,
                description=desc, 
                cover_image_url=img, 
                teacher_id=teacher.id,
                category_id=categories[cat_slug].id,
                status="published"
            )
            db.session.add(c)
            db.session.commit()
            for j in range(1, 4):
                l = Lesson(course_id=c.id, title=f"Bài học {j}: {title}", sequence_order=j)
                db.session.add(l)
            db.session.commit()
            recalc_total_lessons(c.id)

    all_students = db.session.query(User).filter(User.role == "student").all()
    all_courses = db.session.query(Course).all()
    
    if all_students and all_courses:
        for s in all_students:
            log_exists = db.session.query(LearningLog).filter_by(user_id=s.id).first()
            if log_exists:
                continue
                
            k_val = random.randint(1, len(all_courses))
            for c in random.sample(all_courses, k=k_val):
                exists = db.session.query(Enrollment).filter_by(user_id=s.id, course_id=c.id).first()
                if not exists:
                    db.session.add(Enrollment(user_id=s.id, course_id=c.id, status="active"))
                    db.session.commit()
                    lessons = db.session.query(Lesson).filter_by(course_id=c.id).all()
                    for l in lessons:
                        if random.random() > 0.3:
                            db.session.add(LearningLog(user_id=s.id, lesson_id=l.id, action_type="start", timestamp=_utcnow() - timedelta(days=random.randint(0, 7))))
                        if random.random() > 0.5:
                            db.session.add(LearningLog(user_id=s.id, lesson_id=l.id, action_type="complete", timestamp=_utcnow() - timedelta(days=random.randint(0, 7))))
                    db.session.commit()

    return "Seeded rich demo data successfully with Categories and enhanced Course info."
