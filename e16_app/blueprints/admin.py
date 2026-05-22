# -*- coding: utf-8 -*-
import csv
import io
import json
import re
import random
import string
import os
from flask import Blueprint, flash, redirect, render_template, request, url_for, make_response, current_app
from flask_login import current_user
from sqlalchemy import func

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import User, Category, Course, SystemSetting, AuditLog, Enrollment, VALID_ROLES
from ..pagination import get_pagination, paginate_query
from ..services.audit import log_action
from ..services.settings import flush_settings_cache
from ..time_utils import utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text

# --- User Management ---

@bp.route("/users")
@login_required
@role_required("admin")
def list_users():
    page, per_page = get_pagination()
    sort_by = request.args.get("sort_by", "created_at")
    order = request.args.get("order", "desc")

    query = db.session.query(User)

    # Map sort column safely
    if sort_by == "role":
        col = User.role
    elif sort_by == "last_login":
        col = User.last_login
    else:
        sort_by = "created_at"
        col = User.created_at

    if order == "asc":
        query = query.order_by(col.asc())
    else:
        order = "desc"
        query = query.order_by(col.desc())

    pagination = paginate_query(query, page, per_page)
    return render_template(
        "admin_users.html",
        users=pagination["items"],
        pagination=pagination,
        sort_by=sort_by,
        order=order
    )

@bp.post("/users/<user_id>/update_role")
@login_required
@role_required("admin")
def update_user_role(user_id):
    if user_id == current_user.id:
        flash("Bạn không thể tự thay đổi role của chính mình.", "error")
        return redirect(url_for("admin.list_users"))
    user = db.session.get(User, user_id)
    new_role = request.form.get("role")
    if user and new_role in VALID_ROLES:
        old_role = user.role
        user.role = new_role
        db.session.commit()
        log_action("user_role_changed", "User", user_id, {"old": old_role, "new": new_role})
        flash(f"Đã cập nhật role cho {user.email}.", "success")
    return redirect(url_for("admin.list_users"))

@bp.post("/users/<user_id>/delete")
@login_required
@role_required("admin")
def delete_user(user_id):
    if user_id == current_user.id:
        flash("Bạn không thể tự xóa tài khoản của chính mình.", "error")
        return redirect(url_for("admin.list_users"))
    user = db.session.get(User, user_id)
    if user:
        email = user.email
        user.is_active = False
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        log_action("user_soft_deleted", "User", user_id, {"email": email})
        flash(f"Đã vô hiệu hóa người dùng {email}.", "success")
    return redirect(url_for("admin.list_users"))

@bp.post("/users/<user_id>/toggle_status")
@login_required
@role_required("admin")
def toggle_user_status(user_id):
    if user_id == current_user.id:
        flash("Bạn không thể tự vô hiệu hóa tài khoản của chính mình.", "error")
        return redirect(url_for("admin.list_users"))

    user = db.session.get(User, user_id)
    if user:
        user.is_active = not user.is_active
        db.session.commit()
        status_str = "kích hoạt" if user.is_active else "vô hiệu hóa"
        flash(f"Đã {status_str} tài khoản {user.email}.", "success")
        log_action("user_status_changed", "User", user_id, {"new_status": user.is_active})
    return redirect(url_for("admin.list_users"))

# --- Category Management ---

@bp.route("/categories")
@login_required
@role_required("admin")
def list_categories():
    categories = db.session.query(Category).order_by(Category.sort_order.asc()).all()
    return render_template("admin_categories.html", categories=categories)

@bp.post("/categories/new")
@login_required
@role_required("admin")
def create_category():
    name = request.form.get("name")
    icon = request.form.get("icon", "📚")
    description = request.form.get("description", "")
    slug = slugify(name)

    # Ensure unique slug
    base_slug = slug
    counter = 1
    while db.session.query(Category).filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    cat = Category(name=name, slug=slug, icon=icon, description=description)
    db.session.add(cat)
    db.session.commit()
    log_action("category_created", "Category", cat.id, {"name": name})
    flash("Đã tạo danh mục mới.", "success")
    return redirect(url_for("admin.list_categories"))

@bp.post("/categories/<cat_id>/edit")
@login_required
@role_required("admin")
def edit_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if cat:
        cat.name = request.form.get("name")
        cat.icon = request.form.get("icon")
        cat.description = request.form.get("description")
        cat.sort_order = int(request.form.get("sort_order", 0))
        db.session.commit()
        flash("Đã cập nhật danh mục.", "success")
    return redirect(url_for("admin.list_categories"))

@bp.post("/categories/<cat_id>/delete")
@login_required
@role_required("admin")
def delete_category(cat_id):
    # Check if any course is using it
    course_count = db.session.query(Course).filter_by(category_id=cat_id, is_deleted=False).count()
    if course_count > 0:
        flash(f"Không thể xóa danh mục này vì đang có {course_count} khóa học sử dụng.", "error")
        return redirect(url_for("admin.list_categories"))

    cat = db.session.get(Category, cat_id)
    if cat:
        db.session.delete(cat)
        db.session.commit()
        flash("Đã xóa danh mục.", "success")
    return redirect(url_for("admin.list_categories"))

# --- System Settings ---

@bp.route("/settings")
@login_required
@role_required("admin")
def view_settings():
    settings = db.session.query(SystemSetting).all()
    return render_template("admin_settings.html", settings=settings)

@bp.post("/settings/update")
@login_required
@role_required("admin")
def update_settings():
    for key, value in request.form.items():
        setting = db.session.query(SystemSetting).filter_by(key=key).first()
        if setting:
            setting.value = value

    db.session.commit()
    flush_settings_cache()
    log_action("settings_updated")
    flash("Đã cập nhật cấu hình hệ thống.", "success")
    return redirect(url_for("admin.view_settings"))

# --- Audit Logs ---

@bp.route("/audit-log")
@login_required
@role_required("admin")
def view_audit_log():
    page, per_page = get_pagination(default_per_page=50, max_per_page=200)
    query = db.session.query(AuditLog, User).outerjoin(User, User.id == AuditLog.actor_id).order_by(AuditLog.created_at.desc())
    pagination = paginate_query(query, page, per_page)
    return render_template("admin_audit_log.html", logs=pagination["items"], pagination=pagination)

# --- User Import & Creation (Phase 2) ---

def _gen_temp_password(length: int = 10) -> str:
    """Generate a random temporary password."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def _send_welcome_email(email: str, temp_password: str, role: str):
    """Try to send a welcome email.  Silently falls back to logger."""
    from ..urls import app_url_for
    try:
        if current_app.config.get("MAIL_USERNAME"):
            from ..services.mail import send_email
            send_email(
                to=email,
                subject="E16 LMS — Tài khoản mới",
                template_name="welcome_account",
                email=email,
                temp_password=temp_password,
                role=role,
                login_url=app_url_for("auth.login"),
                site_name=current_app.config.get("SITE_NAME", "E16 LMS"),
            )
        else:
            if current_app.debug:
                current_app.logger.debug(
                    f"Welcome email for {email}: temp_password={temp_password}"
                )
    except Exception as e:
        current_app.logger.error(f"Failed to send welcome email to {email}: {e}")


@bp.route("/users/create", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_user():
    from werkzeug.security import generate_password_hash
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "").strip().lower()
        phone = request.form.get("phone", "").strip() or None
        course_id = request.form.get("course_id", "").strip() or None

        if not email or "@" not in email:
            flash("Email không hợp lệ.", "error")
            courses = db.session.query(Course).filter_by(is_deleted=False).all()
            return render_template("admin_create_user.html", courses=courses)

        if role not in VALID_ROLES:
            flash("Vai trò không hợp lệ.", "error")
            courses = db.session.query(Course).filter_by(is_deleted=False).all()
            return render_template("admin_create_user.html", courses=courses)

        exists = db.session.query(User).filter_by(email=email).first()
        if exists:
            flash("Email này đã được sử dụng.", "error")
            courses = db.session.query(Course).filter_by(is_deleted=False).all()
            return render_template("admin_create_user.html", courses=courses)

        temp_pass = _gen_temp_password()
        hashed = generate_password_hash(temp_pass)

        user = User(
            email=email,
            password_hash=hashed,
            temp_password_hash=hashed,
            role=role,
            phone=phone,
            must_change_password=True,
            created_by=current_user.id,
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()

        if course_id and role == "student":
            course = db.session.get(Course, course_id)
            if course and not course.is_deleted and course.status in ("published", "running"):
                from ..services.payment import can_enroll
                from ..time_utils import utcnow
                ok, msg = can_enroll(course, user)
                if ok:
                    existing = db.session.query(Enrollment).filter_by(
                        user_id=user.id, course_id=course_id
                    ).first()
                    if not existing:
                        enroll = Enrollment(
                            user_id=user.id,
                            course_id=course_id,
                            status="active",
                            amount_paid=course.price if course else 0,
                            payment_method="direct_admin",
                            approved_by=current_user.id,
                            approved_at=utcnow(),
                        )
                        db.session.add(enroll)
                        db.session.flush()

                        from ..models import PaymentTransaction
                        tx = PaymentTransaction(
                            enrollment_id=enroll.id,
                            user_id=user.id,
                            course_id=course_id,
                            amount=course.price if course else 0,
                            payment_method="direct_admin",
                            status="approved",
                            processed_by=current_user.id,
                            processed_at=utcnow(),
                            notes="Admin ghi danh trực tiếp"
                        )
                        db.session.add(tx)
                else:
                    flash(f"Không thể ghi danh vào khóa học: {msg}", "warning")

        db.session.commit()
        _send_welcome_email(email, temp_pass, role)

        log_action("create_user_by_admin", "User", user.id, {
            "email": email,
            "role": role,
            "actor": current_user.email
        })

        flash(f"Tạo tài khoản thành công cho {email}. Mật khẩu tạm: {temp_pass}", "success")
        return redirect(url_for("admin.list_users"))

    courses = db.session.query(Course).filter(Course.status.in_(["published", "running"]), Course.is_deleted == False).all()
    return render_template("admin_create_user.html", courses=courses)


@bp.route("/users/import")
@login_required
@role_required("admin")
def import_users_view():
    return render_template("admin_import_users.html")


@bp.post("/users/import")
@login_required
@role_required("admin")
def import_users():
    file = request.files.get("file")
    if not file or not file.filename.endswith('.csv'):
        flash("Vui lòng tải lên file CSV hợp lệ.", "error")
        return redirect(url_for("admin.import_users_view"))

    raw = file.stream.read()
    max_import_size = int(os.getenv("CSV_IMPORT_MAX_BYTES", str(5 * 1024 * 1024)))
    if len(raw) > max_import_size:
        flash("File CSV vượt quá dung lượng cho phép.", "error")
        return redirect(url_for("admin.import_users_view"))

    try:
        stream = io.StringIO(raw.decode("utf-8-sig"), newline=None)
    except UnicodeDecodeError:
        flash("File CSV phải dùng encoding UTF-8.", "error")
        return redirect(url_for("admin.import_users_view"))

    csv_input = csv.DictReader(stream)
    required_headers = {"email", "role"}
    headers = {h.strip() for h in (csv_input.fieldnames or []) if h}
    if not required_headers.issubset(headers):
        flash("CSV phải có header bắt buộc: email, role.", "error")
        return redirect(url_for("admin.import_users_view"))

    success_count = 0
    error_count = 0
    results = []
    max_rows = int(os.getenv("CSV_IMPORT_MAX_ROWS", "5000"))

    from werkzeug.security import generate_password_hash

    for index, row in enumerate(csv_input, start=1):
        if index > max_rows:
            error_count += 1
            results.append({"email": "", "status": "Lỗi", "reason": f"CSV vượt quá giới hạn {max_rows} dòng"})
            break

        email = (row.get("email") or "").strip().lower()
        role = (row.get("role") or "student").strip().lower()
        phone = (row.get("phone") or "").strip() or None
        course_id = (row.get("course_id") or "").strip() or None
        is_active_raw = (row.get("is_active") or "true").strip().lower()

        if not email or "@" not in email:
            error_count += 1
            results.append({"email": email, "status": "Lỗi", "reason": "Email không hợp lệ"})
            continue

        if role not in VALID_ROLES:
            error_count += 1
            results.append({"email": email, "status": "Lỗi", "reason": "Role không hợp lệ"})
            continue

        exists = db.session.query(User).filter_by(email=email).first()
        if exists:
            error_count += 1
            results.append({"email": email, "status": "Bỏ qua", "reason": "Email đã tồn tại"})
            continue

        temp_pass = _gen_temp_password()
        hashed = generate_password_hash(temp_pass)

        user = User(
            email=email,
            password_hash=hashed,
            temp_password_hash=hashed,
            role=role,
            phone=phone,
            is_active=is_active_raw not in {"false", "0", "no", "inactive"},
            must_change_password=True,
            created_by=current_user.id,
        )
        db.session.add(user)
        db.session.flush()

        # Auto-enroll student if course_id provided
        if course_id and role == "student":
            course = db.session.get(Course, course_id)
            if course and not course.is_deleted and course.status in ("published", "running"):
                from ..services.payment import can_enroll
                from ..time_utils import utcnow
                ok, msg = can_enroll(course, user)
                if ok:
                    existing = db.session.query(Enrollment).filter_by(
                        user_id=user.id, course_id=course_id
                    ).first()
                    if not existing:
                        enroll = Enrollment(
                            user_id=user.id,
                            course_id=course_id,
                            status="active",
                            amount_paid=course.price if course else 0,
                            payment_method="direct_admin",
                            approved_by=current_user.id,
                            approved_at=utcnow(),
                        )
                        db.session.add(enroll)
                        db.session.flush()

                        from ..models import PaymentTransaction
                        tx = PaymentTransaction(
                            enrollment_id=enroll.id,
                            user_id=user.id,
                            course_id=course_id,
                            amount=course.price if course else 0,
                            payment_method="direct_admin",
                            status="approved",
                            processed_by=current_user.id,
                            processed_at=utcnow(),
                            notes="Admin import bulk enrollment"
                        )
                        db.session.add(tx)

        _send_welcome_email(email, temp_pass, role)
        success_count += 1
        results.append({"email": email, "temp_pass": temp_pass, "status": "Thành công"})

    db.session.commit()
    log_action("bulk_import", detail={"success": success_count, "errors": error_count})

    flash(f"Import hoàn tất: {success_count} thành công, {error_count} lỗi/bỏ qua.", "success")
    return render_template("admin_import_results.html", results=results)

# --- Course Approval (Phase 2) ---

@bp.route("/courses/pending")
@login_required
@role_required("admin")
def pending_courses():
    courses = db.session.query(Course, User).join(User, User.id == Course.teacher_id).filter(
        Course.status == "pending_review",
        Course.is_deleted == False,
    ).all()
    return render_template("admin_pending_courses.html", courses=courses)

@bp.post("/courses/<course_id>/approve")
@login_required
@role_required("admin")
def approve_course(course_id):
    from ..services.course_lifecycle import transition_course, InvalidTransitionError
    try:
        transition_course(course_id, "approved", current_user.id)
        transition_course(course_id, "published", current_user.id)
        flash("Đã duyệt khóa học.", "success")
    except InvalidTransitionError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.pending_courses"))

@bp.post("/courses/<course_id>/reject")
@login_required
@role_required("admin")
def reject_course(course_id):
    from ..services.course_lifecycle import transition_course, InvalidTransitionError
    note = request.form.get("rejection_note")
    try:
        transition_course(course_id, "rejected", current_user.id, note)
        flash("Đã từ chối khóa học.", "info")
    except InvalidTransitionError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.pending_courses"))

@bp.route("/seed", methods=["GET", "POST"])
def seed_system():
    # Security: Block seeding entirely in production — return 404 to hide route existence.
    app_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "production")).lower()
    if app_env == "production":
        from flask import abort
        abort(404)

    # Allow seeding without login ONLY if no users exist in the DB (initial setup)
    user_count = db.session.query(User).count()
    if user_count > 0:
        # If users exist, require admin role
        from flask_login import current_user
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Bạn cần quyền Admin để chạy lại lệnh Seed.", "error")
            return redirect(url_for("auth.login"))

    if request.method != "POST":
        from flask import render_template_string
        return render_template_string('''
            {% extends "base.html" %}
            {% block content %}
            <div class="card" style="max-width: 600px; margin: 40px auto; padding: 24px; text-align: center;">
                <h2>Xác nhận khởi tạo dữ liệu mẫu</h2>
                <p style="color: var(--text-muted); margin-bottom: 24px;">Hành động này sẽ thêm danh mục cấu hình và các tài khoản mẫu vào cơ sở dữ liệu.</p>
                <form action="{{ url_for('admin.seed_system') }}" method="post">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                    <button type="submit" class="btn btn-primary" style="width: 100%; padding: 12px;">Khởi động Seed</button>
                </form>
            </div>
            {% endblock %}
        ''')

    # Read seed password from environment — never hardcode in production
    seed_password = os.getenv("E16_SEED_PASSWORD") or "demo-password"

    # Seed Categories
    cats = [
        {"name": "Công nghệ thông tin", "slug": "it", "icon": "💻", "sort_order": 1},
        {"name": "Kinh doanh & Khởi nghiệp", "slug": "business", "icon": "📈", "sort_order": 2},
        {"name": "Ngoại ngữ", "slug": "languages", "icon": "🌍", "sort_order": 3},
        {"name": "Thiết kế đồ họa", "slug": "design", "icon": "🎨", "sort_order": 4}
    ]
    for c_data in cats:
        if not db.session.query(Category).filter_by(slug=c_data["slug"]).first():
            db.session.add(Category(**c_data))

    # Seed Settings
    settings = [
        {"key": "site_name", "value": "E16 LMS", "description": "Tên nền tảng hiển thị trên tiêu đề và sidebar."},
        {"key": "site_logo_url", "value": "https://images.unsplash.com/photo-1614850523296-d8c1af93d400?q=80&w=2070&auto=format&fit=crop", "description": "URL ảnh logo của hệ thống."},
        {"key": "allow_registration", "value": "True", "description": "Cho phép người dùng tự đăng ký tài khoản."},
        {"key": "require_course_approval", "value": "True", "description": "Yêu cầu admin duyệt khóa học trước khi xuất bản."}
    ]
    for s_data in settings:
        if not db.session.query(SystemSetting).filter_by(key=s_data["key"]).first():
            db.session.add(SystemSetting(**s_data))

    # Seed Users — read password from env var, never hardcode
    from werkzeug.security import generate_password_hash
    is_local = not os.environ.get("VERCEL") and app_env in ("development", "testing")

    if is_local:
        users = [
            {"email": "admin_local@e16.local", "password_hash": generate_password_hash("admin_local_pass"), "role": "admin", "must_change_password": False},
            {"email": "teacher_local@e16.local", "password_hash": generate_password_hash("teacher_local_pass"), "role": "teacher", "must_change_password": False},
            {"email": "student_local@e16.local", "password_hash": generate_password_hash("student_local_pass"), "role": "student", "must_change_password": False},
            {"email": "hocvu_local@e16.local", "password_hash": generate_password_hash("hocvu_local_pass"), "role": "hoc_vu", "must_change_password": False},
        ]
    else:
        users = [
            {"email": "admin@e16.local", "password_hash": generate_password_hash(seed_password), "role": "admin", "must_change_password": False},
            {"email": "teacher@e16.local", "password_hash": generate_password_hash(seed_password), "role": "teacher", "must_change_password": False},
            {"email": "student@e16.local", "password_hash": generate_password_hash(seed_password), "role": "student", "must_change_password": False},
            {"email": "hocvu@e16.local", "password_hash": generate_password_hash(seed_password), "role": "hoc_vu", "must_change_password": False},
        ]

    for u_data in users:
        if not db.session.query(User).filter_by(email=u_data["email"]).first():
            db.session.add(User(**u_data))

    for i in range(1, 6):
        email = f"student_local{i}@e16.local" if is_local else f"student{i}@e16.local"
        pwd = "student_local_pass" if is_local else seed_password
        if not db.session.query(User).filter_by(email=email).first():
            db.session.add(User(email=email, password_hash=generate_password_hash(pwd), role="student"))

    db.session.commit()
    flush_settings_cache()
    flash("Đã khởi tạo dữ liệu mẫu hệ thống thành công.", "success")
    return redirect(url_for("admin.view_settings"))


@bp.route("/reports")
@login_required
@role_required("admin")
def list_reports():
    from ..models import ContentReport, User
    page, per_page = get_pagination(default_per_page=20, max_per_page=100)
    status_filter = request.args.get("status", "pending")

    query = db.session.query(ContentReport, User).join(User, User.id == ContentReport.reporter_id)
    if status_filter:
        query = query.filter(ContentReport.status == status_filter)

    query = query.order_by(ContentReport.created_at.desc())
    pagination = paginate_query(query, page, per_page)

    # Optimized: batch-fetch all threads/replies/authors to avoid N+1 queries
    from ..models import ForumThread, ForumReply
    items = pagination["items"]

    # Collect all target IDs by type
    thread_ids = {r.target_id for r, _ in items if r.target_type == "thread"}
    reply_ids = {r.target_id for r, _ in items if r.target_type == "reply"}

    # Batch fetch in 2 queries max
    threads_map = {}
    replies_map = {}
    if thread_ids:
        for t in db.session.query(ForumThread).filter(ForumThread.id.in_(thread_ids)).all():
            threads_map[t.id] = t
    if reply_ids:
        for rep in db.session.query(ForumReply).filter(ForumReply.id.in_(reply_ids)).all():
            replies_map[rep.id] = rep
        # Also fetch threads referenced by replies
        reply_thread_ids = {rep.thread_id for rep in replies_map.values()}
        missing_thread_ids = reply_thread_ids - set(threads_map.keys())
        if missing_thread_ids:
            for t in db.session.query(ForumThread).filter(ForumThread.id.in_(missing_thread_ids)).all():
                threads_map[t.id] = t

    # Batch fetch all author users
    author_ids = set()
    for t in threads_map.values():
        author_ids.add(t.author_id)
    for rep in replies_map.values():
        author_ids.add(rep.author_id)
    users_map = {}
    if author_ids:
        for u in db.session.query(User).filter(User.id.in_(author_ids)).all():
            users_map[u.id] = u

    enriched_items = []
    for report, reporter in items:
        target_body = ""
        target_author = ""
        course_id = ""
        if report.target_type == "thread":
            thread = threads_map.get(report.target_id)
            if thread:
                target_body = f"Chu de: {thread.title}\n\nNoi dung: {thread.body}"
                author = users_map.get(thread.author_id)
                target_author = author.email if author else "Khong ro"
                course_id = thread.course_id
        elif report.target_type == "reply":
            reply = replies_map.get(report.target_id)
            if reply:
                target_body = reply.body
                author = users_map.get(reply.author_id)
                target_author = author.email if author else "Khong ro"
                thread = threads_map.get(reply.thread_id)
                course_id = thread.course_id if thread else ""

        enriched_items.append({
            "report": report,
            "reporter": reporter,
            "target_body": target_body,
            "target_author": target_author,
            "course_id": course_id
        })

    return render_template(
        "admin_reports.html",
        items=enriched_items,
        pagination=pagination,
        current_status=status_filter
    )


@bp.post("/reports/<report_id>/resolve")
@login_required
@role_required("admin")
def resolve_report(report_id):
    from ..models import ContentReport, ForumThread, ForumReply
    report = db.session.get(ContentReport, report_id)
    if not report:
        flash("Không tìm thấy báo cáo.", "error")
        return redirect(url_for("admin.list_reports"))

    action = request.form.get("action")  # "hide" or "dismiss"
    if action not in ("hide", "dismiss"):
        flash("Hành động không hợp lệ.", "error")
        return redirect(url_for("admin.list_reports"))

    report.status = "resolved" if action == "hide" else "dismissed"
    report.resolved_at = utcnow()
    report.resolved_by = current_user.id
    report.action_taken = action

    if action == "hide":
        if report.target_type == "thread":
            thread = db.session.get(ForumThread, report.target_id)
            if thread:
                thread.is_hidden = True
                log_action("forum_thread_hidden_by_report", "ForumThread", thread.id)
        elif report.target_type == "reply":
            reply = db.session.get(ForumReply, report.target_id)
            if reply:
                reply.is_hidden = True
                log_action("forum_reply_hidden_by_report", "ForumReply", reply.id)

    db.session.commit()
    log_action("report_resolved", "ContentReport", report_id, {"action": action})
    flash("Đã xử lý báo cáo thành công.", "success")
    return redirect(url_for("admin.list_reports", status=request.args.get("status", "pending")))
