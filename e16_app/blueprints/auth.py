import os
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, oauth, limiter
from ..models import Course, Enrollment, LearningLog, Lesson, User
from ..services.course import recalc_total_lessons
from ..services.logging import logger

bp = Blueprint("auth", __name__)


@bp.route("/login/google")
def google_login():
    redirect_uri = url_for("auth.google_authorize", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route("/login/google/authorize")
def google_authorize():
    token = oauth.google.authorize_access_token()
    user_info = token.get("userinfo")
    if not user_info:
        flash("Không thể lấy thông tin từ Google.", "error")
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

    user.last_login = datetime.utcnow()
    user.login_count = (user.login_count or 0) + 1
    db.session.commit()

    login_user(user)
    logger.log("login_google", user_id=user.id, user_email=user.email, metadata={"method": "google"})
    flash(f"Chào mừng {email}!", "success")
    return redirect(url_for("auth.home"))


@bp.route("/test-flash")
def test_flash():
    flash("Đây là thông báo Thành công!", "success")
    flash("Đây là thông báo Lỗi!", "error")
    flash("Đây là thông báo Thông tin!", "info")
    return redirect(url_for("auth.login"))


@bp.route("/")
def home():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.role == "student":
        return redirect(url_for("student.dashboard"))
    if current_user.role == "teacher":
        return redirect(url_for("teacher.manage_courses"))
    return redirect(url_for("analytics.dashboard"))


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")
        # Security: chỉ cho phép student hoặc teacher tự đăng ký
        if role not in {"student", "teacher"}:
            role = "student"
        if not email or not password:
            flash("Email và mật khẩu là bắt buộc.", "error")
            return redirect(url_for("auth.register"))
        if db.session.query(User).filter(User.email == email).first():
            flash("Email đã tồn tại.", "error")
            return redirect(url_for("auth.register"))
        user = User(email=email, password_hash=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.commit()
        logger.log("register", user_id=user.id, user_email=user.email, metadata={"role": role})
        flash("Đăng ký thành công. Mời đăng nhập.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.session.query(User).filter(User.email == email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Email hoặc mật khẩu không chính xác.", "error")
            return redirect(url_for("auth.login"))
        user.last_login = datetime.utcnow()
        user.login_count = (user.login_count or 0) + 1
        db.session.commit()
        login_user(user)
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
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            # Security: chỉ log trong chế độ debug, không bao giờ dùng print
            if current_app.debug:
                current_app.logger.debug(f"Password reset link for {email}: {reset_url}")
            # TODO: Gửi email thật trong production bằng Flask-Mail
        # Security: luôn trả về thông báo chung để chống email enumeration
        flash("Nếu email tồn tại trong hệ thống, một liên kết đặt lại mật khẩu sẽ được gửi.", "info")
        return redirect(url_for("auth.login"))
    return render_template("forgot_password.html", user=None)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = db.session.query(User).filter(User.reset_token == token, User.reset_token_expiry > datetime.utcnow()).first()
    if not user:
        flash("Liên kết không hợp lệ hoặc đã hết hạn.", "error")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        password = request.form.get("password", "")
        if not password:
            flash("Mật khẩu không được để trống.", "error")
            return redirect(url_for("auth.reset_password", token=token))
        user.password_hash = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash("Mật khẩu đã được cập nhật. Vui lòng đăng nhập lại.", "success")
        return redirect(url_for("auth.login"))
    return render_template("reset_password.html", token=token, user=None)


@bp.route("/seed")
def seed():
    import random
    from ..models import Category
    
    # Security: Require key to seed
    seed_password = os.getenv("E16_SEED_PASSWORD", "demo-password")
    request_key = request.args.get("key")
    if request_key != seed_password:
        return "Unauthorized: Invalid seed key.", 403

    # Safe initialization
    db.create_all() 
    
    # Create Categories
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

    # Create extra student accounts if they don't exist
    students = []
    for i in range(1, 6):
        email = f"student{i}@e16.local"
        if not db.session.query(User).filter(User.email == email).first():
            s = User(email=email, password_hash=generate_password_hash(seed_password), role="student")
            students.append(s)
    if students:
        db.session.add_all(students)
        db.session.commit()

    # Create roles if missing
    teacher = db.session.query(User).filter_by(email="teacher@e16.local").first()
    if not teacher:
        teacher = User(email="teacher@e16.local", password_hash=generate_password_hash(seed_password), role="teacher")
        db.session.add(teacher)
    
    admin = db.session.query(User).filter_by(email="admin@e16.local").first()
    if not admin:
        admin = User(email="admin@e16.local", password_hash=generate_password_hash(seed_password), role="admin")
        db.session.add(admin)
    db.session.commit()

    # Diverse courses
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
            # Add some lessons to each
            for j in range(1, 4):
                l = Lesson(course_id=c.id, title=f"Bài học {j}: {title}", sequence_order=j)
                db.session.add(l)
            db.session.commit()
            recalc_total_lessons(c.id)

    # Randomized Learning Logs for Analytics
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
                            db.session.add(LearningLog(user_id=s.id, lesson_id=l.id, action_type="start", timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 7))))
                        if random.random() > 0.5:
                            db.session.add(LearningLog(user_id=s.id, lesson_id=l.id, action_type="complete", timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 7))))
                    db.session.commit()

    return "Seeded rich demo data successfully with Categories and enhanced Course info."

    return "Seeded rich demo data successfully without resetting existing tables."
