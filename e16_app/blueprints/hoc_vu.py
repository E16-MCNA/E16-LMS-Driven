# -*- coding: utf-8 -*-
"""
Blueprint for Học vụ (Academic Affairs) role.

Provides: account creation (single + CSV), course approval,
and dashboard overview.  Accessible by `hoc_vu` and `admin` roles.
"""
import csv
import io
import os
import random
import string

from flask import (
    Blueprint, current_app, flash, redirect,
    render_template, request, url_for,
)
from flask_login import current_user
from werkzeug.security import generate_password_hash

from ..auth_utils import login_required, role_required
from ..extensions import db
from ..models import (
    VALID_ROLES, Course, Enrollment, User,
)
from ..pagination import get_pagination, paginate_query
from ..services.audit import log_action
from ..time_utils import utcnow

bp = Blueprint("hoc_vu", __name__, url_prefix="/hoc-vu")

# Roles that Học vụ is allowed to create (cannot create admin or hoc_vu)
CREATABLE_ROLES = {"student", "teacher", "le_tan", "ke_toan"}


def _gen_temp_password(length: int = 10) -> str:
    """Generate a random temporary password."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def _send_welcome_email(email: str, temp_password: str, role: str):
    """Try to send a welcome email.  Silently falls back to logger."""
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
                login_url=url_for("auth.login", _external=True),
                site_name=current_app.config.get("SITE_NAME", "E16 LMS"),
            )
        else:
            if current_app.debug:
                current_app.logger.debug(
                    f"Welcome email for {email}: temp_password={temp_password}"
                )
    except Exception as e:
        current_app.logger.error(f"Failed to send welcome email to {email}: {e}")


# ── Dashboard ────────────────────────────────────────────

@bp.route("/dashboard")
@login_required
@role_required("hoc_vu", "admin")
def dashboard():
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = db.session.query(User).count()
    pending_courses = db.session.query(Course).filter(
        Course.status == "pending_review",
        Course.is_deleted == False,
    ).count()
    accounts_today = db.session.query(User).filter(
        User.created_by.isnot(None),
        User.created_at >= today_start,
    ).count()
    active_courses = db.session.query(Course).filter(
        Course.status.in_(["published", "running"]),
        Course.is_deleted == False,
    ).count()

    recent_users = (
        db.session.query(User)
        .filter(User.created_by.isnot(None))
        .order_by(User.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "hocvu_dashboard.html",
        total_users=total_users,
        pending_courses=pending_courses,
        accounts_created_today=accounts_today,
        active_courses=active_courses,
        recent_users=recent_users,
    )


# ── Single account creation ─────────────────────────────

@bp.route("/accounts/create", methods=["GET", "POST"])
@login_required
@role_required("hoc_vu", "admin")
def create_account():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        full_name = (request.form.get("full_name") or "").strip()
        phone = (request.form.get("phone") or "").strip() or None
        role = (request.form.get("role") or "student").strip().lower()
        course_id = (request.form.get("course_id") or "").strip() or None

        # Validation
        if not email or "@" not in email:
            flash("Email không hợp lệ.", "error")
            return redirect(url_for("hoc_vu.create_account"))

        allowed_roles = VALID_ROLES if current_user.role == "admin" else CREATABLE_ROLES
        if role not in allowed_roles:
            flash(f"Role '{role}' không hợp lệ. Chỉ được tạo: {', '.join(sorted(allowed_roles))}.", "error")
            return redirect(url_for("hoc_vu.create_account"))

        if db.session.query(User).filter_by(email=email).first():
            flash("Email đã tồn tại trong hệ thống.", "error")
            return redirect(url_for("hoc_vu.create_account"))

        # Create user
        temp_pass = _gen_temp_password()
        user = User(
            email=email,
            password_hash=generate_password_hash(temp_pass),
            role=role,
            phone=phone,
            must_change_password=True,
            created_by=current_user.id,
            temp_password_hash=generate_password_hash(temp_pass),
        )
        db.session.add(user)
        db.session.commit()

        # Auto-enroll if course_id given and role is student
        if course_id and role == "student":
            course = db.session.get(Course, course_id)
            if course and not course.is_deleted:
                existing = db.session.query(Enrollment).filter_by(
                    user_id=user.id, course_id=course_id
                ).first()
                if not existing:
                    db.session.add(Enrollment(
                        user_id=user.id, course_id=course_id, status="active"
                    ))
                    db.session.commit()

        # Send welcome email
        _send_welcome_email(email, temp_pass, role)

        log_action("account_created_by_hocvu", "User", user.id, {
            "email": email, "role": role, "created_by": current_user.email,
        })

        flash(
            f"Tạo tài khoản thành công cho {email}. "
            f"Mật khẩu tạm: {temp_pass}",
            "success",
        )
        return redirect(url_for("hoc_vu.create_account"))

    # GET — render form
    courses = (
        db.session.query(Course)
        .filter(Course.status.in_(["published", "running", "approved"]),
                Course.is_deleted == False)
        .order_by(Course.title)
        .all()
    )
    return render_template("hocvu_create_account.html", courses=courses)


# ── Account list ─────────────────────────────────────────

@bp.route("/accounts")
@login_required
@role_required("hoc_vu", "admin")
def list_accounts():
    page, per_page = get_pagination()
    query = (
        db.session.query(User)
        .filter(User.created_by.isnot(None))
        .order_by(User.created_at.desc())
    )
    pagination = paginate_query(query, page, per_page)
    return render_template(
        "hocvu_accounts.html",
        users=pagination["items"],
        pagination=pagination,
    )


# ── CSV import ───────────────────────────────────────────

@bp.post("/accounts/<user_id>/reset-temp-password")
@login_required
@role_required("hoc_vu", "admin")
def reset_temp_password(user_id):
    user = db.session.get(User, user_id)
    if not user or user.created_by is None:
        flash("Khong tim thay tai khoan do Hoc vu tao.", "error")
        return redirect(url_for("hoc_vu.list_accounts"))

    if user.role not in CREATABLE_ROLES:
        flash("Khong duoc cap lai mat khau tam cho role nay.", "error")
        return redirect(url_for("hoc_vu.list_accounts"))

    temp_pass = _gen_temp_password()
    password_hash = generate_password_hash(temp_pass)
    user.password_hash = password_hash
    user.temp_password_hash = password_hash
    user.must_change_password = True
    user.is_active = True
    db.session.commit()

    _send_welcome_email(user.email, temp_pass, user.role)
    log_action("temp_password_reset_by_hocvu", "User", user.id, {
        "email": user.email,
        "role": user.role,
        "created_by": current_user.email,
    })

    flash(f"Da cap lai mat khau tam cho {user.email}: {temp_pass}", "success")
    return redirect(url_for("hoc_vu.list_accounts"))


@bp.route("/accounts/import", methods=["GET"])
@login_required
@role_required("hoc_vu", "admin")
def import_accounts_view():
    return render_template("hocvu_import.html")


@bp.route("/accounts/import", methods=["POST"])
@login_required
@role_required("hoc_vu", "admin")
def import_accounts():
    file = request.files.get("file")
    if not file or not file.filename.endswith(".csv"):
        flash("Vui lòng tải lên file CSV hợp lệ.", "error")
        return redirect(url_for("hoc_vu.import_accounts_view"))

    raw = file.stream.read()
    max_size = int(os.getenv("CSV_IMPORT_MAX_BYTES", str(5 * 1024 * 1024)))
    if len(raw) > max_size:
        flash("File CSV vượt quá dung lượng cho phép.", "error")
        return redirect(url_for("hoc_vu.import_accounts_view"))

    try:
        stream = io.StringIO(raw.decode("utf-8-sig"), newline=None)
    except UnicodeDecodeError:
        flash("File CSV phải dùng encoding UTF-8.", "error")
        return redirect(url_for("hoc_vu.import_accounts_view"))

    csv_input = csv.DictReader(stream)
    required_headers = {"email", "role"}
    headers = {h.strip() for h in (csv_input.fieldnames or []) if h}
    if not required_headers.issubset(headers):
        flash("CSV phải có header bắt buộc: email, role.", "error")
        return redirect(url_for("hoc_vu.import_accounts_view"))

    max_rows = int(os.getenv("CSV_IMPORT_MAX_ROWS", "5000"))
    success_count = 0
    error_count = 0
    results = []

    for index, row in enumerate(csv_input, start=1):
        if index > max_rows:
            error_count += 1
            results.append({
                "email": "", "role": "",
                "status": "Lỗi",
                "reason": f"CSV vượt quá giới hạn {max_rows} dòng",
            })
            break

        email = (row.get("email") or "").strip().lower()
        role = (row.get("role") or "student").strip().lower()
        full_name = (row.get("full_name") or "").strip()
        phone = (row.get("phone") or "").strip() or None
        course_id = (row.get("course_id") or "").strip() or None

        if not email or "@" not in email:
            error_count += 1
            results.append({"email": email, "role": role, "status": "Lỗi", "reason": "Email không hợp lệ"})
            continue

        if role not in CREATABLE_ROLES:
            error_count += 1
            results.append({"email": email, "role": role, "status": "Lỗi",
                            "reason": f"Role không hợp lệ (cho phép: {', '.join(sorted(CREATABLE_ROLES))})"})
            continue

        if db.session.query(User).filter_by(email=email).first():
            error_count += 1
            results.append({"email": email, "role": role, "status": "Bỏ qua", "reason": "Email đã tồn tại"})
            continue

        temp_pass = _gen_temp_password()
        user = User(
            email=email,
            password_hash=generate_password_hash(temp_pass),
            role=role,
            phone=phone,
            must_change_password=True,
            created_by=current_user.id,
            temp_password_hash=generate_password_hash(temp_pass),
        )
        db.session.add(user)
        db.session.flush()  # get user.id for enrollment

        # Auto-enroll student if course_id provided
        if course_id and role == "student":
            course = db.session.get(Course, course_id)
            if course and not course.is_deleted:
                existing = db.session.query(Enrollment).filter_by(
                    user_id=user.id, course_id=course_id
                ).first()
                if not existing:
                    db.session.add(Enrollment(
                        user_id=user.id, course_id=course_id, status="active"
                    ))

        _send_welcome_email(email, temp_pass, role)
        success_count += 1
        results.append({
            "email": email, "role": role,
            "temp_pass": temp_pass, "status": "Thành công",
        })

    db.session.commit()
    log_action("bulk_import_by_hocvu", detail={
        "success": success_count, "errors": error_count,
        "actor": current_user.email,
    })

    flash(f"Import hoàn tất: {success_count} thành công, {error_count} lỗi/bỏ qua.", "success")
    return render_template("hocvu_import_results.html", results=results)


# ── Course approval ──────────────────────────────────────

@bp.route("/courses/pending")
@login_required
@role_required("hoc_vu", "admin")
def pending_courses():
    courses = (
        db.session.query(Course, User)
        .join(User, User.id == Course.teacher_id)
        .filter(
            Course.status == "pending_review",
            Course.is_deleted == False,
        )
        .all()
    )
    return render_template("hocvu_pending_courses.html", courses=courses)


@bp.route("/courses/<course_id>/review", methods=["POST"])
@login_required
@role_required("hoc_vu", "admin")
def review_course(course_id):
    from ..services.course_lifecycle import transition_course, InvalidTransitionError

    action = request.form.get("action")  # "approve" or "reject"
    note = request.form.get("review_note", "").strip()

    if action == "approve":
        try:
            transition_course(course_id, "approved", current_user.id, note or None)
            flash("Đã duyệt khóa học.", "success")
        except InvalidTransitionError as e:
            flash(str(e), "error")

    elif action == "reject":
        if not note:
            flash("Vui lòng nhập lý do từ chối.", "error")
            return redirect(url_for("hoc_vu.pending_courses"))
        try:
            transition_course(course_id, "rejected", current_user.id, note)
            flash("Đã từ chối khóa học.", "info")
        except InvalidTransitionError as e:
            flash(str(e), "error")
    else:
        flash("Hành động không hợp lệ.", "error")

    return redirect(url_for("hoc_vu.pending_courses"))
